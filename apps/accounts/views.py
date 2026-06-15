import logging
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from django_ratelimit.decorators import ratelimit
from apps.core.middleware import get_client_ip
from django.db.models import Sum
from apps.core.logging import log_step

logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
def profile_view(request):
    user = request.user
    errors = []
    form_data = {}
    open_modal = None

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'personal':
            username = request.POST.get('username', '').strip()
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()

            if not username:
                errors.append('Username is required.')
            elif User.objects.filter(username__iexact=username).exclude(pk=user.pk).exists():
                errors.append('That username is already taken.')
            elif not username.replace('_', '').replace('.', '').isalnum():
                errors.append('Username may only contain letters, numbers, underscores and dots.')

            if not errors:
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                user.phone_number = phone_number
                user.save(update_fields=['username', 'first_name', 'last_name', 'phone_number'])
                messages.success(request, 'Personal information updated.')
                log_step('account', 'profile_updated', request)
                return redirect('accounts:profile')
            else:
                open_modal = 'personal'
                form_data = {'username': username, 'first_name': first_name,
                             'last_name': last_name, 'phone_number': phone_number}

        elif form_type == 'address':
            street_address = request.POST.get('street_address', '').strip()
            city = request.POST.get('city', '').strip()
            county = request.POST.get('county', '').strip()

            user.street_address = street_address
            user.city = city
            user.county = county
            user.save(update_fields=['street_address', 'city', 'county'])
            messages.success(request, 'Delivery address updated.')
            log_step('account', 'address_updated', request)
            return redirect('accounts:profile')

    # Order stats
    orders_qs = user.order_set.all()
    total_orders = orders_qs.count()
    total_spent = orders_qs.aggregate(s=Sum('total'))['s'] or 0
    recent_orders = orders_qs.order_by('-created_at')[:3]

    return render(request, 'accounts/profile.html', {
        'user': user,
        'errors': errors,
        'form_data': form_data,
        'open_modal': open_modal,
        'total_orders': total_orders,
        'total_spent': total_spent,
        'recent_orders': recent_orders,
    })


@login_required
def order_history_view(request):
    qs = request.user.order_set.order_by('-created_at').prefetch_related('items')
    paginator = Paginator(qs, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'accounts/order_history.html', {'page_obj': page})


@login_required
@ratelimit(key=get_client_ip, rate='10/m', block=True)
def check_username(request):
    """API endpoint to check username availability."""
    from django.http import JsonResponse
    username = request.GET.get('username', '').strip()
    current_user_id = request.user.id if request.user.is_authenticated else None
    
    if not username:
        return JsonResponse({'available': None, 'message': ''})
    
    if len(username) < 3:
        return JsonResponse({'available': False, 'message': 'Username must be at least 3 characters'})
    
    if not username.replace('_', '').replace('.', '').isalnum():
        return JsonResponse({'available': False, 'message': 'Only letters, numbers, underscores and dots allowed'})
    
    exists = User.objects.filter(username__iexact=username).exclude(pk=current_user_id).exists()
    
    if exists:
        return JsonResponse({'available': False, 'message': 'Username is already taken'})
    else:
        return JsonResponse({'available': True, 'message': 'Username is available'})
