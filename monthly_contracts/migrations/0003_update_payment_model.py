from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0001_initial'),
        ('monthly_contracts', '0002_initial'),
    ]

    operations = [
        # Primero eliminar el campo payment_method antiguo (varchar)
        migrations.RemoveField(
            model_name='contractpayment',
            name='payment_method',
        ),
        # Agregar el nuevo campo payment_method como ForeignKey
        migrations.AddField(
            model_name='contractpayment',
            name='payment_method',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='contract_payments',
                to='parking.paymentmethod',
                verbose_name='Método de pago'
            ),
        ),
        # Agregar campos nuevos
        migrations.AddField(
            model_name='contractpayment',
            name='amount_received',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Monto recibido'),
        ),
        migrations.AddField(
            model_name='contractpayment',
            name='change_amount',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Cambio'),
        ),
        migrations.AddField(
            model_name='contractpayment',
            name='period_end',
            field=models.DateField(blank=True, null=True, verbose_name='Fin del período'),
        ),
        migrations.AddField(
            model_name='contractpayment',
            name='period_start',
            field=models.DateField(blank=True, null=True, verbose_name='Inicio del período'),
        ),
        migrations.AddField(
            model_name='contractpayment',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now, verbose_name='Fecha de registro'),
            preserve_default=False,
        ),
        # Agregar métodos al modelo MonthlyContract
        migrations.AlterField(
            model_name='contractpayment',
            name='payment_date',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='Fecha de pago'),
        ),
    ]
