from decimal import Decimal
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from .models import (
    User, Product, Category, Supplier, Customer,
    StockMovement, MovementType, PaymentMethod, UserRole
)


class LoginForm(forms.Form):
    """
    Authentication form supporting login via either Username or Email address.
    """
    username_or_email = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your username or email',
            'autofocus': True,
            'id': 'login-identifier'
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Enter your password',
            'id': 'login-password'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        identifier = cleaned_data.get('username_or_email')
        password = cleaned_data.get('password')

        if identifier and password:
            # Check if identifier matches email
            user = None
            if '@' in identifier:
                try:
                    user_obj = User.objects.get(email__iexact=identifier)
                    user = authenticate(username=user_obj.username, password=password)
                except User.DoesNotExist:
                    pass
            
            if not user:
                user = authenticate(username=identifier, password=password)

            if not user:
                raise ValidationError("Invalid credentials. Please verify your username/email and password.")
            if not user.is_active or not user.active:
                raise ValidationError("This account has been deactivated. Please contact the administrator.")

            cleaned_data['user'] = user
        return cleaned_data


class ProductForm(forms.ModelForm):
    """
    Form for adding and editing gift shop products with strict price validations.
    """
    class Meta:
        model = Product
        fields = [
            'code', 'name', 'category', 'supplier',
            'cost_price', 'selling_price', 'stock_qty',
            'reorder_level', 'active'
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. SKU-GFT-101'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Handmade Ceramic Mug'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'selling_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'stock_qty': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        cost = cleaned_data.get('cost_price')
        selling = cleaned_data.get('selling_price')

        if cost is not None and selling is not None:
            if selling < cost:
                raise ValidationError({
                    'selling_price': f"Selling price (${selling:.2f}) cannot be less than cost price (${cost:.2f})."
                })
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Souvenirs & Ornaments'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional category description...'}),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'phone', 'email', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier Company / Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+1 (555) 000-0000'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'supplier@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Warehouse/office address...'}),
        }


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['name', 'phone', 'email']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Customer Full Name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address (Optional)'}),
        }


class StockInForm(forms.Form):
    """
    Form for receiving inventory shipments from suppliers.
    """
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Units received'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    cost_price = forms.DecimalField(
        required=False,
        min_value=Decimal('0.00'),
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Leave blank to retain current cost'})
    )
    reason = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PO / Invoice # or Restock details'})
    )


class StockAdjustmentForm(forms.Form):
    """
    Form for manual inventory audits and damage adjustments.
    """
    new_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'New verified stock count'})
    )
    reason = forms.CharField(
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Physical count audit, Damaged during display'})
    )


class UserCreationCustomForm(UserCreationForm):
    """
    Admin form for registering new employees with specific roles.
    """
    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Employee Full Name'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'employee@luxegifts.com'})
    )
    role = forms.ChoiceField(
        choices=UserRole.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['username', 'name', 'email', 'role']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique Username'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.name = self.cleaned_data['name']
        user.email = self.cleaned_data['email']
        user.role = self.cleaned_data['role']
        user.active = True
        if commit:
            user.save()
        return user


class SalesReportFilterForm(forms.Form):
    """
    Filter form for sales reporting.
    """
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    cashier = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        empty_label="All Staff / Cashiers",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
