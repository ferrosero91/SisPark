"""
Add database index on ParkingTicket.placa for placa__iexact lookups.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('parking', '0009_vehiclecategory_minimum_minutes_and_more'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='parkingticket',
            index=models.Index(fields=['placa'], name='idx_ticket_placa'),
        ),
    ]
