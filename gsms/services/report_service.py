from decimal import Decimal
from django.db import models
from django.db.models import Sum, Count, F, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from gsms.models import Sale, SaleItem, Payment, Product, Category, SaleStatus


class ReportService:
    """
    Application / Business Logic Layer for Reports and Business Intelligence.
    Provides analytics for Sales, Profitability, Inventory turnover, and Staff performance.
    """

    @classmethod
    def get_dashboard_metrics(cls):
        """
        Gathers high-level KPIs for the main dashboard.
        """
        today = timezone.now().date()
        start_of_today = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        start_of_month = timezone.make_aware(datetime(today.year, today.month, 1))

        # Today's Sales
        today_sales_qs = Sale.objects.filter(sale_date__gte=start_of_today, status=SaleStatus.COMPLETED)
        today_revenue = today_sales_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        today_count = today_sales_qs.count()

        # Month's Sales
        month_sales_qs = Sale.objects.filter(sale_date__gte=start_of_month, status=SaleStatus.COMPLETED)
        month_revenue = month_sales_qs.aggregate(total=Sum('total'))['total'] or Decimal('0.00')
        month_count = month_sales_qs.count()

        # All-Time Revenue
        all_time_revenue = Sale.objects.filter(
            status=SaleStatus.COMPLETED
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        # Low Stock & Out of Stock counts
        low_stock_count = Product.objects.filter(
            active=True,
            stock_qty__lte=models.F('reorder_level')
        ).count()

        total_products = Product.objects.filter(active=True).count()

        # Recent 5 transactions
        recent_sales = Sale.objects.filter(
            status=SaleStatus.COMPLETED
        ).select_related('user', 'customer').order_by('-sale_date')[:5]

        # Top 5 best selling items this month
        top_items = SaleItem.objects.filter(
            sale__sale_date__gte=start_of_month,
            sale__status=SaleStatus.COMPLETED
        ).values('product__name', 'product__code').annotate(
            total_qty=Sum('quantity'),
            total_revenue=Sum('line_total')
        ).order_by('-total_qty')[:5]

        # Last 7 days trend for Chart.js
        seven_days_ago = today - timedelta(days=6)
        daily_trends = []
        for i in range(7):
            day_date = seven_days_ago + timedelta(days=i)
            day_start = timezone.make_aware(datetime.combine(day_date, datetime.min.time()))
            day_end = timezone.make_aware(datetime.combine(day_date, datetime.max.time()))
            day_rev = Sale.objects.filter(
                sale_date__gte=day_start,
                sale_date__lte=day_end,
                status=SaleStatus.COMPLETED
            ).aggregate(t=Sum('total'))['t'] or Decimal('0.00')
            daily_trends.append({
                'label': day_date.strftime('%b %d'),
                'revenue': float(day_rev)
            })

        return {
            'today_revenue': today_revenue,
            'today_count': today_count,
            'month_revenue': month_revenue,
            'month_count': month_count,
            'all_time_revenue': all_time_revenue,
            'low_stock_count': low_stock_count,
            'total_products': total_products,
            'recent_sales': recent_sales,
            'top_items': list(top_items),
            'daily_trends': daily_trends,
        }

    @classmethod
    def get_sales_report(cls, start_date=None, end_date=None, user_id=None, status=SaleStatus.COMPLETED):
        """
        Generates detailed filtered sales report with totals, payment methods breakdown,
        and line items summary.
        """
        qs = Sale.objects.all()

        if status:
            qs = qs.filter(status=status)

        if start_date:
            start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
            qs = qs.filter(sale_date__gte=start_dt)

        if end_date:
            end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            qs = qs.filter(sale_date__lte=end_dt)

        if user_id:
            qs = qs.filter(user_id=user_id)

        aggregates = qs.aggregate(
            gross_subtotal=Sum('subtotal'),
            total_discount=Sum('discount'),
            net_total=Sum('total'),
            total_orders=Count('sale_id'),
            avg_order_value=Avg('total')
        )

        # Payment methods breakdown
        payments_breakdown = Payment.objects.filter(
            sale__in=qs
        ).values('method').annotate(
            total_amount=Sum('amount'),
            tx_count=Count('payment_id')
        )

        return {
            'sales': qs.select_related('user', 'customer').order_by('-sale_date'),
            'gross_subtotal': aggregates['gross_subtotal'] or Decimal('0.00'),
            'total_discount': aggregates['total_discount'] or Decimal('0.00'),
            'net_total': aggregates['net_total'] or Decimal('0.00'),
            'total_orders': aggregates['total_orders'] or 0,
            'avg_order_value': aggregates['avg_order_value'] or Decimal('0.00'),
            'payments_breakdown': payments_breakdown,
        }
