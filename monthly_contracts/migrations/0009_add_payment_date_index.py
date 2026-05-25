"""
Add database index on ContractPayment.payment_date for date range queries.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_contracts', '0008_remove_monthlycontract_category_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='contractpayment',
            index=models.Index(fields=['payment_date'], name='idx_payment_date'),
        ),
    ]
