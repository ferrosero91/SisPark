"""
Add database index on ThirdPartyVehicle.plate for plate__iexact lookups.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('third_parties', '0002_alter_thirdparty_tenant'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='thirdpartyvehicle',
            index=models.Index(fields=['plate'], name='idx_vehicle_plate'),
        ),
    ]
