from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un superusuario por defecto si no existe ninguno'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            default='admin@solupark.com',
            help='Email del superusuario (default: admin@solupark.com)'
        )
        parser.add_argument(
            '--password',
            default='Admin123*',
            help='Contraseña del superusuario (default: Admin123*)'
        )

    def handle(self, *args, **options):
        email = options['email']
        password = options['password']
        
        # Verificar si ya existe algún superusuario
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(
                self.style.WARNING('Ya existe un superusuario. No se creó uno nuevo.')
            )
            return
        
        # Crear superusuario
        user = User.objects.create_superuser(
            email=email,
            password=password,
            first_name='Super',
            last_name='Admin',
            must_change_password=True
        )
        
        self.stdout.write(
            self.style.SUCCESS(f'Superusuario creado exitosamente:')
        )
        self.stdout.write(f'  Email: {email}')
        self.stdout.write(f'  Contraseña: {password}')
        self.stdout.write(
            self.style.WARNING('  ¡IMPORTANTE: Cambie la contraseña en el primer login!')
        )
