from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied

# Data Analysis Imports
import pandas as pd
import numpy as np

# PDF Generation Imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# Model Imports
from .models import Appointment, Doctor, Department

# --- DASHBOARD & PUBLIC VIEWS ---

@login_required
def dashboard(request):
    """Main hub showing high-level stats for TODAY only."""
    today = timezone.localdate()
    # Explicitly filter by today and status to ensure counts are accurate
    total_pending = Appointment.objects.filter(status='Pending', registration_time__date=today).count()
    total_consulted = Appointment.objects.filter(status='Consulted', registration_time__date=today).count()
    doctors_count = Doctor.objects.count()
    
    context = {
        'total_pending': total_pending,
        'total_consulted': total_consulted,
        'doctors_count': doctors_count,
    }
    return render(request, 'appointments/dashboard.html', context)

@login_required
def register_patient(request):
    """Handles patient registration with Department-to-Doctor filtering logic."""
    doctors = Doctor.objects.all()
    departments = Department.objects.all()

    if request.method == "POST":
        p_name = request.POST.get('name')
        p_age = request.POST.get('age')
        doc_id = request.POST.get('doctor')
        is_emergency = request.POST.get('emergency') == 'on'
        
        if not doc_id:
            messages.error(request, "Please select a department and a doctor.")
            return redirect('register_patient')

        selected_doc = get_object_or_404(Doctor, id=doc_id)
        
        # Calculate wait time only based on TODAY'S pending patients
        current_queue_count = Appointment.objects.filter(
            doctor=selected_doc, 
            status='Pending',
            registration_time__date=timezone.localdate()
        ).count()
        
        est_wait = current_queue_count * 15
        consultation_time = timezone.now() + timedelta(minutes=est_wait)

        new_app = Appointment.objects.create(
            patient_name=p_name,
            age=p_age,
            doctor=selected_doc,
            is_emergency=is_emergency,
            estimated_time=consultation_time
        )
        messages.success(request, f"Token generated successfully for {p_name}!")
        return render(request, 'appointments/success.html', {'appointment': new_app})
        
    return render(request, 'appointments/register.html', {
        'doctors': doctors, 
        'departments': departments
    })

@login_required
def search_patient(request):
    """Search patients by Name or Token Number."""
    query = request.GET.get('q')
    results = None
    if query:
        results = Appointment.objects.filter(
            Q(patient_name__icontains=query) | 
            Q(token_number__iexact=query)
        ).order_by('-registration_time')
    return render(request, 'appointments/search.html', {'results': results, 'query': query})

# --- DOCTOR SECURE QUEUE MANAGEMENT ---

@login_required
def doctor_queues(request):
    """Displays queues for Pending patients only."""
    today = timezone.localdate()
    
    if request.user.is_superuser:
        doctors = Doctor.objects.all()
        queues = {
            doc: Appointment.objects.filter(
                doctor=doc, 
                status='Pending',
                registration_time__date=today
            ).order_by('-is_emergency', 'registration_time') 
            for doc in doctors
        }
    elif hasattr(request.user, 'doctor'):
        logged_in_doctor = request.user.doctor
        queues = {
            logged_in_doctor: Appointment.objects.filter(
                doctor=logged_in_doctor, 
                status='Pending',
                registration_time__date=today
            ).order_by('-is_emergency', 'registration_time')
        }
    else:
        # Fallback for staff
        doctors = Doctor.objects.all()
        queues = {
            doc: Appointment.objects.filter(
                doctor=doc, 
                status='Pending',
                registration_time__date=today
            ).order_by('-is_emergency', 'registration_time') 
            for doc in doctors
        }

    return render(request, 'appointments/queues.html', {'queue_data': queues})

@login_required
def mark_consulted(request, appointment_id):
    """Update status. Once saved, patient becomes invisible to 'Pending' filters."""
    appointment = get_object_or_404(Appointment, id=appointment_id)
    is_assigned_doctor = hasattr(request.user, 'doctor') and appointment.doctor == request.user.doctor
    
    if request.user.is_superuser or is_assigned_doctor:
        appointment.status = 'Consulted'
        appointment.save() # Once saved, QuerySets with status='Pending' will automatically exclude this
        messages.success(request, f"Patient {appointment.patient_name} marked as consulted.")
    else:
        messages.error(request, "Permission Denied.")
        
    return redirect('doctor_queues')

# --- PREMIUM ANALYTICS & PDF EXPORT ---

@login_required
def analytics_report(request):
    """Workload analytics. Lists ONLY patients who are still waiting."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    today = timezone.localdate()
    doctors = Doctor.objects.all()
    workload_data = []

    for doc in doctors:
        # 🔑 CRITICAL FIX: Explicitly filter for 'Pending'
        # This makes checked patients 'invisible' in the workload list
        active_waiting_list = Appointment.objects.filter(
            doctor=doc, 
            status='Pending',
            registration_time__date=today
        ).order_by('-is_emergency', 'registration_time')
        
        workload_data.append({
            'doctor__name': doc.name,
            'doctor__department__name': doc.department.name if doc.department else "General",
            'total_patients': active_waiting_list.count(),
            'patient_list': active_waiting_list 
        })

    # Department aggregation: counts pending vs consulted separately
    dept_workload = Department.objects.annotate(
        pending_count=Count('doctor__appointment', filter=Q(
            doctor__appointment__status='Pending', 
            doctor__appointment__registration_time__date=today
        )),
        consulted_count=Count('doctor__appointment', filter=Q(
            doctor__appointment__status='Consulted', 
            doctor__appointment__registration_time__date=today
        ))
    ).order_by('-pending_count')

    return render(request, 'appointments/analytics.html', {
        'workload': workload_data,
        'dept_workload': dept_workload
    })

@login_required
def department_analytics(request):
    return redirect('analytics_report')

@login_required
def export_pdf(request):
    """Generates PDF for ALL patients today (Consulted + Pending)."""
    if not request.user.is_superuser:
        raise PermissionDenied()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="OPD_Daily_Summary.pdf"'

    doc = SimpleDocTemplate(response, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    today = timezone.localdate()

    elements.append(Paragraph("MedQueue Pro - Daily OPD Summary Report", styles['Title']))
    elements.append(Paragraph(f"Date: {today.strftime('%d %B, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 12))

    today_apps = Appointment.objects.filter(registration_time__date=today)
    
    summary_data = [[
        Paragraph(f"<b>Total Patients:</b> {today_apps.count()}", styles['Normal']),
        Paragraph(f"<b>Emergencies:</b> {today_apps.filter(is_emergency=True).count()}", styles['Normal']),
        Paragraph(f"<b>Consulted:</b> {today_apps.filter(status='Consulted').count()}", styles['Normal'])
    ]]
    summary_table = Table(summary_data, colWidths=[150, 150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("<b>Complete Patient Log (Today):</b>", styles['Heading3']))
    data = [['Token', 'Patient Name', 'Age', 'Doctor', 'Status']]
    for app in today_apps.order_by('registration_time'):
        data.append([f"#{app.token_number}", app.patient_name, str(app.age), f"Dr. {app.doctor.name}", app.status])

    main_table = Table(data, colWidths=[60, 140, 50, 140, 80])
    main_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.dodgerblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    
    elements.append(main_table)
    doc.build(elements)
    return response