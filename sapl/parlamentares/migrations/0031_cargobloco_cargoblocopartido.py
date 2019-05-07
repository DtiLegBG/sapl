# -*- coding: utf-8 -*-
# Generated by Django 1.11.20 on 2019-05-31 14:09
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('parlamentares', '0030_auto_20190531_0848'),
    ]

    operations = [
        migrations.CreateModel(
            name='CargoBloco',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=80, verbose_name='Nome do Cargo')),
                ('unico', models.BooleanField(choices=[(True, 'Sim'), (False, 'Não')], default=True, verbose_name='Cargo Único')),
                ('descricao', models.TextField(blank=True, verbose_name='Descrição')),
            ],
        ),
        migrations.CreateModel(
            name='CargoBlocoPartido',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data_inicio', models.DateField(verbose_name='Data Início')),
                ('data_fim', models.DateField(blank=True, null=True, verbose_name='Data Fim')),
                ('bloco', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='parlamentares.Bloco')),
                ('cargo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='parlamentares.CargoBloco')),
                ('parlamentar', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='parlamentares.Parlamentar')),
            ],
        ),
    ]
