# Generated by Django 4.2.21 on 2025-05-23 23:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('problems', '0005_alter_problem_constraints_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='problem',
            name='constraints',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AlterField(
            model_name='problem',
            name='objective_coefficients',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
