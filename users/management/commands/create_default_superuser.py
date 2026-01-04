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
            help='Contraseña del superusuario (si no se proporciona, se genera una aleatoria)'
        )

    def handle(self, *args, **options):
        import secrets
        import string
        
        email = options['email']
        password = options['password']
        
        # Si no se proporciona contraseña, generar una segura
        if not password:
            alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
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
