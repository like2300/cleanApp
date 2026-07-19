from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Reclamation, Notification
from accounts.models import User
from django.http import JsonResponse
from django.utils import timezone

from core.utils import get_zone_queryset

@login_required
def reclamation_list(request):
    user = request.user
    if user.role == User.Role.CLIENT:
        reclamations = Reclamation.objects.filter(user=user).order_by('-created_at')
    else:
        # Use common utility for staff roles
        reclamations = get_zone_queryset(user, Reclamation.objects.all(), zone_field='user__zone').order_by('-created_at')
        
    return render(request, 'notifications/reclamation_list.html', {'reclamations': reclamations})

@login_required
def reclamation_detail(request, pk):
    user = request.user
    reclamation = get_object_or_404(Reclamation, pk=pk)
    
    # Access control
    if user.role in [User.Role.SUPER_ADMIN, User.Role.ACCOUNTANT, User.Role.SHAREHOLDER]:
        pass # All access
    elif user.role == User.Role.ZONE_MANAGER:
        if not reclamation.user or not user.zones.filter(id=reclamation.user.zone.id).exists():
            messages.error(request, "Accès refusé.")
            return redirect('reclamation_list')
    elif user.is_staff:
        pass # Generic staff fallback
    else:
        if reclamation.user != user:
            messages.error(request, "Accès refusé.")
            return redirect('reclamation_list')
    
    # SHAREHOLDER cannot modify status
    can_edit_status = user.role in [User.Role.SUPER_ADMIN, User.Role.ACCOUNTANT, User.Role.ZONE_MANAGER]
    
    if request.method == 'POST' and can_edit_status:
        new_status = request.POST.get('status')
        if new_status in Reclamation.Status.values:
            reclamation.status = new_status
            reclamation.save()
            messages.success(request, f"Statut mis à jour : {reclamation.get_status_display()}")
            
            # Notify the user
            if reclamation.user:
                Notification.objects.create(
                    user=reclamation.user,
                    title="Mise à jour Réclamation",
                    message=f"Votre réclamation '{reclamation.subject}' est passée au statut : {reclamation.get_status_display()}",
                    synced=False
                )
            
            return redirect('reclamation_detail', pk=pk)
            
    return render(request, 'notifications/reclamation_detail.html', {
        'reclamation': reclamation,
        'can_edit_status': can_edit_status
    })

@login_required
def reclamation_create(request):
    if request.method == 'POST':
        subject = request.POST.get('subject')
        description = request.POST.get('description')
        if subject and description:
            reclamation = Reclamation.objects.create(
                user=request.user,
                subject=subject,
                description=description,
                synced=False
            )
            
            # Notify staff
            staff_users = User.objects.filter(role__in=[User.Role.SUPER_ADMIN, User.Role.ZONE_MANAGER, User.Role.ACCOUNTANT])
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title="Nouvelle Réclamation",
                    message=f"Le client {request.user.username} a soumis une réclamation : {subject}",
                    synced=False
                )
            
            messages.success(request, "Votre réclamation a été soumise avec succès.")
            return redirect('reclamation_list')
    return render(request, 'notifications/reclamation_form.html')

@login_required
def get_unread_notifications(request):
    notifs = Notification.objects.filter(user=request.user, is_read=False).order_by('-created_at')
    data = [{
        'id': n.id,
        'title': n.title,
        'message': n.message,
        'created_at': n.created_at.strftime('%H:%M')
    } for n in notifs]
    return JsonResponse({'notifications': data, 'count': len(data)})

@login_required
def mark_notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    return JsonResponse({'status': 'success'})

def public_reclamation(request):
    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
            name = data.get('name')
            contact = data.get('contact')
            message = data.get('message')
            
            if not message:
                return JsonResponse({'error': 'Message requis'}, status=400)

            reclamation = Reclamation.objects.create(
                guest_name=name,
                guest_contact=contact,
                subject="Réclamation Invité",
                description=message,
                synced=False
            )

            # Notify staff
            staff_users = User.objects.filter(role__in=[User.Role.SUPER_ADMIN, User.Role.ZONE_MANAGER])
            for staff in staff_users:
                Notification.objects.create(
                    user=staff,
                    title="Nouvelle Réclamation Invité",
                    message=f"Un invité ({name or 'Anonyme'}) a envoyé un message.",
                    synced=False
                )
            
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)
