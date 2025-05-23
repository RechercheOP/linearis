# Generated by Django 4.2.21 on 2025-05-24 12:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('problems', '0011_alter_problem_objective_coefficients_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problem',
            name='status',
            field=models.CharField(choices=[('optimal', 'Solution optimale trouvée'), ('infeasible', 'Problème infaisable'), ('unbounded', 'Problème non borné'), ('error', 'Erreur lors de la résolution'), ('unsupported', 'Type de problème non supporté'), ('pending', 'En attente de résolution')], default='pending', max_length=20),
        ),
    ]
