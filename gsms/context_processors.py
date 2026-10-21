from django.db import models
from .models import Product

def shop_context(request):
    """
    Context processor providing store branding, notification counters,
    and role badges across all templates.
    """
    context = {
        'SHOP_NAME': 'LuxeGifts Studio & Boutique',
        'SHOP_TAGLINE': 'Curated Gifts, Keepsakes & Souvenirs',
        'SHOP_PHONE': '+1 (555) 789-GIFT',
        'SHOP_EMAIL': 'contact@luxegifts.com',
        'SHOP_ADDRESS': '124 Artisan Avenue, Suite 400, New York, NY',
    }
    if request.user.is_authenticated:
        # Low stock notification count
        try:
            low_stock_count = Product.objects.filter(active=True, stock_qty__lte=models.F('reorder_level')).count()
        except Exception:
            low_stock_count = 0
        context['low_stock_count'] = low_stock_count
        context['user_role'] = getattr(request.user, 'role', 'Staff')
    return context
