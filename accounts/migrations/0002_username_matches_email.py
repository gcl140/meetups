from django.db import migrations


def set_username_to_email(apps, schema_editor):
    User = apps.get_model('accounts', 'User')
    for user in User.objects.all():
        if user.username != user.email:
            user.username = user.email
            user.save(update_fields=['username'])


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(set_username_to_email, migrations.RunPython.noop),
    ]
