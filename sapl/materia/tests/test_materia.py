from datetime import date
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import File
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.db.models import Max
from django.utils.translation import ugettext_lazy as _
from model_mommy import mommy
import datetime, pytest, os

from sapl.base.models import Autor, TipoAutor
from sapl.comissoes.models import Comissao, TipoComissao
from sapl.materia.models import (Anexada, Autoria, DespachoInicial,
                                 DocumentoAcessorio, MateriaLegislativa,
                                 Numeracao, Proposicao, RegimeTramitacao,
                                 StatusTramitacao, TipoDocumento,
                                 TipoMateriaLegislativa, TipoProposicao,
                                 Tramitacao, UnidadeTramitacao)
from sapl.materia.forms import (TramitacaoForm, compara_tramitacoes_mat, 
                                TramitacaoUpdateForm)
from sapl.norma.models import (LegislacaoCitada, NormaJuridica,
                               TipoNormaJuridica)
from sapl.parlamentares.models import Legislatura
from sapl.utils import (models_with_gr_for_model, lista_anexados,
                        gerar_hash_arquivo,SEPARADOR_HASH_PROPOSICAO)


@pytest.mark.django_db(transaction=False)
def test_lista_materias_anexadas():
        tipo_materia = mommy.make(
                TipoMateriaLegislativa,
                descricao="Tipo_Teste"
        )
        regime_tramitacao = mommy.make(
                RegimeTramitacao,
                descricao="Regime_Teste"
        )
        materia_principal = mommy.make(
                MateriaLegislativa,
                numero=20,
                ano=2018,
                data_apresentacao="2018-01-04",
                regime_tramitacao=regime_tramitacao,
                tipo=tipo_materia
        )
        materia_anexada = mommy.make(
                MateriaLegislativa,
                numero=21,
                ano=2019,
                data_apresentacao="2019-05-04",
                regime_tramitacao=regime_tramitacao,
                tipo=tipo_materia
        )
        materia_anexada_anexada = mommy.make(
                MateriaLegislativa,
                numero=22,
                ano=2020,
                data_apresentacao="2020-01-05",
                regime_tramitacao=regime_tramitacao,
                tipo=tipo_materia
        )

        mommy.make(
                Anexada,
                materia_principal=materia_principal,
                materia_anexada=materia_anexada,
                data_anexacao="2019-05-11"
        )
        mommy.make(
                Anexada,
                materia_principal=materia_anexada,
                materia_anexada=materia_anexada_anexada,
                data_anexacao="2020-11-05"
        )

        lista = lista_anexados(materia_principal)
        
        assert len(lista) == 2
        assert lista[0] == materia_anexada
        assert lista[1] == materia_anexada_anexada


@pytest.mark.django_db(transaction=False)
def make_unidade_tramitacao(descricao):
    # Cria uma comissão para ser a unidade de tramitação
    tipo_comissao = mommy.make(TipoComissao)
    comissao = mommy.make(Comissao,
                          tipo=tipo_comissao,
                          nome=descricao,
                          sigla='T',
                          data_criacao='2016-03-21')

    # Testa a comissão
    assert comissao.tipo == tipo_comissao
    assert comissao.nome == descricao

    # Cria a unidade
    unidade = mommy.make(UnidadeTramitacao, comissao=comissao)
    assert unidade.comissao == comissao

    return unidade


@pytest.mark.django_db(transaction=False)
def make_norma():
    # Cria um novo tipo de Norma
    tipo = mommy.make(TipoNormaJuridica,
                      sigla='T1',
                      descricao='Teste_Tipo_Norma')
    mommy.make(NormaJuridica,
               tipo=tipo,
               numero=1,
               ano=2016,
               data='2016-03-21',
               esfera_federacao='E',
               ementa='Teste_Ementa')

    # Testa se a Norma foi criada
    norma = NormaJuridica.objects.first()
    assert norma.tipo == tipo
    assert norma.numero == '1'
    assert norma.ano == 2016

    return norma


@pytest.mark.django_db(transaction=False)
def make_materia_principal():
    regime_tramitacao = mommy.make(RegimeTramitacao, descricao='Teste_Regime')

    # Cria a matéria principal
    tipo = mommy.make(TipoMateriaLegislativa,
                      sigla='T1',
                      descricao='Teste_MateriaLegislativa')
    mommy.make(MateriaLegislativa,
               tipo=tipo,
               numero='165',
               ano='2002',
               data_apresentacao='2003-01-01',
               regime_tramitacao=regime_tramitacao)

    # Testa matéria
    materia = MateriaLegislativa.objects.first()
    assert materia.numero == 165
    assert materia.ano == 2002

    return materia


@pytest.mark.django_db(transaction=False)
def test_materia_anexada_submit(admin_client):
    materia_principal = make_materia_principal()

    # Cria a matéria que será anexada
    tipo_anexada = mommy.make(TipoMateriaLegislativa,
                              sigla='T2',
                              descricao='Teste_2')
    regime_tramitacao = mommy.make(RegimeTramitacao, descricao='Teste_Regime')
    mommy.make(MateriaLegislativa,
               tipo=tipo_anexada,
               numero='32',
               ano='2004',
               data_apresentacao='2005-11-10',
               regime_tramitacao=regime_tramitacao)

    # Testa se a matéria que será anexada foi criada
    materia_anexada = MateriaLegislativa.objects.get(numero=32, ano=2004)

    # Testa POST
    response = admin_client.post(reverse('sapl.materia:anexada_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'tipo': materia_anexada.tipo.pk,
                                  'numero': materia_anexada.numero,
                                  'ano': materia_anexada.ano,
                                  'data_anexacao': '2016-03-18',
                                  'salvar': 'salvar'},
                                 follow=True)
    assert response.status_code == 200

    # Verifica se a matéria foi anexada corretamente
    anexada = Anexada.objects.first()
    assert anexada.materia_principal == materia_principal
    assert anexada.materia_anexada == materia_anexada


@pytest.mark.django_db(transaction=False)
def test_autoria_submit(admin_client):
    materia_principal = make_materia_principal()
    # Cria um tipo de Autor
    tipo_autor = mommy.make(TipoAutor, descricao='Teste Tipo_Autor')

    # Cria um Autor
    autor = mommy.make(
        Autor,
        tipo=tipo_autor,
        nome='Autor Teste')

    # Testa POST
    response = admin_client.post(
        reverse('sapl.materia:autoria_create',
                kwargs={'pk': materia_principal.pk}),
        {'autor': autor.pk,
         'primeiro_autor': True,
         'materia_id': materia_principal.pk, },
        follow=True)
    assert response.status_code == 200

    # Verifica se o autor foi realmente criado
    autoria = Autoria.objects.first()
    assert autoria.autor == autor
    assert autoria.materia == materia_principal
    assert autoria.primeiro_autor is True


@pytest.mark.django_db(transaction=False)
def test_despacho_inicial_submit(admin_client):
    materia_principal = make_materia_principal()

    # Cria uma comissão
    tipo_comissao = mommy.make(TipoComissao)
    comissao = mommy.make(Comissao,
                          tipo=tipo_comissao,
                          nome='Teste',
                          ativa=True,
                          sigla='T',
                          data_criacao='2016-03-18')

    # Testa POST
    response = admin_client.post(reverse('sapl.materia:despachoinicial_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'comissao': comissao.pk,
                                  'salvar': 'salvar'},
                                 follow=True)
    assert response.status_code == 200

    # Verifica se o despacho foi criado
    despacho = DespachoInicial.objects.first()

    assert despacho.comissao == comissao
    assert despacho.materia == materia_principal


@pytest.mark.django_db(transaction=False)
def test_numeracao_submit(admin_client):
    materia_principal = make_materia_principal()
    materia = make_materia_principal()

    # Testa POST
    response = admin_client.post(reverse('sapl.materia:numeracao_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'tipo_materia': materia.tipo.pk,
                                  'numero_materia': materia.numero,
                                  'ano_materia': materia.ano,
                                  'data_materia': '2016-03-21',
                                  'salvar': 'salvar'},
                                 follow=True)

    assert response.status_code == 200

    # Verifica se a numeração foi criada
    numeracao = Numeracao.objects.first()
    assert numeracao.tipo_materia == materia.tipo
    assert numeracao.ano_materia == materia.ano


@pytest.mark.django_db(transaction=False)
def test_documento_acessorio_submit(admin_client):
    materia_principal = make_materia_principal()

    # Cria um tipo de Autor
    tipo_autor = mommy.make(TipoAutor, descricao='Teste Tipo_Autor')

    # Cria um Autor
    autor = mommy.make(
        Autor,
        tipo=tipo_autor,
        nome='Autor Teste')

    # Cria um tipo de documento
    tipo = mommy.make(TipoDocumento,
                      descricao='Teste')

    # Testa POST
    response = admin_client.post(reverse(
        'sapl.materia:documentoacessorio_create',
        kwargs={'pk': materia_principal.pk}),
        {'tipo': tipo.pk,
         'nome': 'teste_nome',
         'data_materia': '2016-03-21',
         'autor': autor,
         'ementa': 'teste_ementa',
         'data': '2016-03-21',
         'salvar': 'salvar'},
        follow=True)

    assert response.status_code == 200

    # Verifica se o documento foi criado
    doc = DocumentoAcessorio.objects.first()
    assert doc.tipo == tipo
    assert doc.nome == 'teste_nome'
    assert doc.autor == str(autor)


@pytest.mark.django_db(transaction=False)
def test_legislacao_citada_submit(admin_client):
    materia_principal = make_materia_principal()
    norma = make_norma()

    # Testa POST
    response = admin_client.post(
        reverse('sapl.materia:legislacaocitada_create',
                kwargs={'pk': materia_principal.pk}),
        {'tipo': norma.tipo.pk,
         'numero': norma.numero,
         'ano': norma.ano,
         'disposicao': 'disposicao',
         'salvar': 'salvar'},
        follow=True)

    assert response.status_code == 200

    # Testa se a legislação citada foi criada
    leg = LegislacaoCitada.objects.first()
    assert leg.norma == norma


@pytest.mark.django_db(transaction=False)
def test_tramitacao_submit(admin_client):
    materia_principal = make_materia_principal()
    # Cria status para tramitação
    status_tramitacao = mommy.make(StatusTramitacao,
                                   indicador='F',
                                   sigla='ST',
                                   descricao='Status_Teste')
    # Testa POST
    response = admin_client.post(
        reverse('sapl.materia:tramitacao_create',
                kwargs={'pk': materia_principal.pk}),
        {'unidade_tramitacao_local': make_unidade_tramitacao(
            'Unidade Local').pk,
         'unidade_tramitacao_destino': make_unidade_tramitacao(
            'Unidade Destino').pk,
         'urgente': True,
         'status': status_tramitacao.pk,
         'data_tramitacao': '2016-03-21',
         'data_fim_prazo': '2016-03-22',
         'data_encaminhamento': '2016-03-22',
         'texto': 'Texto_Teste',
         'salvar': 'salvar'},
        follow=True)

    assert response.status_code == 200

    # Testa se a tramitacao foi criada
    tramitacao = Tramitacao.objects.first()
    assert (tramitacao.unidade_tramitacao_local.comissao.nome ==
            'Unidade Local')
    assert (tramitacao.unidade_tramitacao_destino.comissao.nome ==
            'Unidade Destino')
    assert tramitacao.urgente is True


@pytest.mark.django_db(transaction=False)
def test_form_errors_anexada(admin_client):
    materia_principal = make_materia_principal()
    response = admin_client.post(reverse('sapl.materia:anexada_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'salvar': 'salvar'},
                                 follow=True)

    assert (response.context_data['form'].errors['tipo'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['numero'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['ano'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['data_anexacao'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_autoria(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(reverse('sapl.materia:autoria_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'materia_id': materia_principal.pk,
                                  'autor_id': '', },
                                 follow=True)

    assert (response.context_data['form'].errors['autor'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_despacho_inicial(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(reverse('sapl.materia:despachoinicial_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'salvar': 'salvar'},
                                 follow=True)

    assert (response.context_data['form'].errors['comissao'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_documento_acessorio(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(
        reverse('sapl.materia:documentoacessorio_create',
                kwargs={'pk': materia_principal.pk}),
        {'salvar': 'salvar'},
        follow=True)

    assert (response.context_data['form'].errors['tipo'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['nome'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_legislacao_citada(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(
        reverse('sapl.materia:legislacaocitada_create',
                kwargs={'pk': materia_principal.pk}),
        {'salvar': 'salvar'},
        follow=True)

    assert (response.context_data['form'].errors['tipo'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['numero'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['ano'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_numeracao(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(reverse('sapl.materia:numeracao_create',
                                         kwargs={'pk': materia_principal.pk}),
                                 {'salvar': 'salvar'},
                                 follow=True)

    assert (response.context_data['form'].errors['tipo_materia'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['numero_materia'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['ano_materia'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['data_materia'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_tramitacao(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(
        reverse('sapl.materia:tramitacao_create',
                kwargs={'pk': materia_principal.pk}),
        {'salvar': 'salvar'},
        follow=True)

    assert (response.context_data['form'].errors['data_tramitacao'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors[
            'unidade_tramitacao_local'] == ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['status'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors[
            'unidade_tramitacao_destino'] == ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['texto'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_form_errors_relatoria(admin_client):
    materia_principal = make_materia_principal()

    response = admin_client.post(
        reverse('sapl.materia:relatoria_create',
                kwargs={'pk': materia_principal.pk}),
        {'salvar': 'salvar'},
        follow=True)

    assert (response.context_data['form'].errors['data_designacao_relator'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['parlamentar'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_proposicao_submit(admin_client):
    tipo_autor = mommy.make(TipoAutor, descricao='Teste Tipo_Autor')
    user = get_user_model().objects.filter(is_active=True)[0]

    autor = mommy.make(
        Autor,
        user=user,
        tipo=tipo_autor,
        nome='Autor Teste')

    file_content = 'file_content'
    texto = SimpleUploadedFile("file.txt", file_content.encode('UTF-8'))

    mcts = ContentType.objects.get_for_models(
        *models_with_gr_for_model(TipoProposicao))

    for pk, mct in enumerate(mcts):
        tipo_conteudo_related = mommy.make(mct, pk=pk + 1)

        response = admin_client.post(
            reverse('sapl.materia:proposicao_create'),
            {'tipo': mommy.make(
                TipoProposicao, pk=3,
                tipo_conteudo_related=tipo_conteudo_related).pk,
             'descricao': 'Teste proposição',
             'justificativa_devolucao': '  ',
             'status': 'E',
             'autor': autor.pk,
             'texto_original': texto,
             'salvar': 'salvar',
             'receber_recibo': 'True',
             },
            follow=True)

        assert response.status_code == 200

        proposicao = Proposicao.objects.first()

        assert proposicao is not None
        assert proposicao.descricao == 'Teste proposição'
        assert proposicao.tipo.pk == 3
        assert proposicao.tipo.tipo_conteudo_related.pk == pk + 1


@pytest.mark.django_db(transaction=False)
def test_form_errors_proposicao(admin_client):
    tipo_autor = mommy.make(TipoAutor, descricao='Teste Tipo_Autor')

    user = get_user_model().objects.filter(is_active=True)[0]

    autor = mommy.make(
        Autor,
        user=user,
        tipo=tipo_autor,
        nome='Autor Teste')

    file_content = 'file_content'
    texto = SimpleUploadedFile("file.txt", file_content.encode('UTF-8'))

    response = admin_client.post(reverse('sapl.materia:proposicao_create'),
                                 {'autor': autor.pk,
                                  'justificativa_devolucao': '  ',
                                  'texto_original': texto,
                                  'salvar': 'salvar'},
                                 follow=True)

    assert (response.context_data['form'].errors['tipo'] ==
            ['Este campo é obrigatório.'])
    assert (response.context_data['form'].errors['descricao'] ==
            ['Este campo é obrigatório.'])


@pytest.mark.django_db(transaction=False)
def test_numeracao_materia_legislativa_por_legislatura(admin_client):

    # Criar Legislaturas
    legislatura1 = mommy.make(Legislatura,
                              data_inicio='2014-01-01',
                              data_fim='2018-12-31',
                              numero=20,
                              data_eleicao='2013-10-15'
                              )
    legislatura2 = mommy.make(Legislatura,
                              data_inicio='2009-01-01',
                              data_fim='2013-12-31',
                              numero=21,
                              data_eleicao='2018-10-15'
                              )

    # Cria uma materia na legislatura1
    tipo_materia = mommy.make(TipoMateriaLegislativa,
                              id=1, sequencia_numeracao='L')
    materia = mommy.make(MateriaLegislativa,
                         tipo=tipo_materia,
                         ano=2017,
                         numero=1,
                         data_apresentacao='2017-03-05'
                         )

    url = reverse('sapl.materia:recuperar_materia')

    # Testa numeração do Materia Legislativa na Legislatura1
    query_params = '?tipo={}&ano={}'.format(materia.tipo.id, materia.ano)
    response = admin_client.get(url + query_params, follow=True)
    response_content = eval(response.content.decode('ascii'))
    esperado_legislatura1 = eval('{"numero": 2, "ano": "2017"}')
    assert response_content['numero'] == esperado_legislatura1['numero']

    # Testa numeração do Materia Legislativa na Legislatura2
    query_params = '?tipo={}&ano={}'.format(1, '2010')
    response = admin_client.get(url + query_params, follow=True)
    response_content = eval(response.content.decode('ascii'))
    esperado_legislatura2 = eval('{"ano": "2010", "numero": 1}')
    assert response_content['numero'] == esperado_legislatura2['numero']


@pytest.mark.django_db(transaction=False)
def test_numeracao_materia_legislativa_por_ano(admin_client):

    # Cria uma materia
    tipo_materia = mommy.make(TipoMateriaLegislativa,
                              id=1, sequencia_numeracao ='A')
    materia = mommy.make(MateriaLegislativa,
                         tipo=tipo_materia,
                         ano=2017,
                         numero=1
                         )

    url = reverse('sapl.materia:recuperar_materia')

    # Testa numeração da Materia Legislativa no ano da materia criada
    query_params = '?tipo={}&ano={}'.format(materia.tipo.id, materia.ano)
    response = admin_client.get(url + query_params, follow=True)
    response_content = eval(response.content.decode('ascii'))
    esperado_ano = eval('{"numero": 2, "ano": "2017"}')
    assert response_content['numero'] == esperado_ano['numero']

    # Testa numeração da Materia Legislativa de outro ano
    query_params = '?tipo={}&ano={}'.format(1, '2010')
    response = admin_client.get(url + query_params, follow=True)
    response_content = eval(response.content.decode('ascii'))
    esperado_outro_ano = eval('{"ano": "2010", "numero": 1}')
    assert response_content['numero'] == esperado_outro_ano['numero']


def gerar_hash(prop, receber_recibo=False):

    prop.save()
    if receber_recibo:
        prop.hash_code = ''
    else:
        if prop.texto_original:
            prop.hash_code = gerar_hash_arquivo(
            prop.texto_original.path, str(prop.pk))
        elif prop.texto_articulado.exists():
            ta = prop.texto_articulado.first()
            prop.hash_code = 'P' + ta.hash() + SEPARADOR_HASH_PROPOSICAO + str(prop.pk)


def criar_materias(ano, tipo):
    # Cria alguma materias
    mommy.make(MateriaLegislativa,
                tipo=tipo,
                ano=ano,
                numero=1
                )
    mommy.make(MateriaLegislativa,
                tipo=tipo,
                ano=ano,
                numero=10
                )
    mommy.make(MateriaLegislativa,
                tipo=tipo,
                ano=ano,
                numero=5
                )

def criar_legislaturas(ano_inicio, ano_fim):
    mommy.make(Legislatura,
               data_inicio='2014-01-01',
               data_fim='2018-12-31',
               numero=20,
              )


def enviar_receber_proposicao(prop, admin_client, numeracao='A'):
    url = reverse('sapl.materia:proposicao_detail', kwargs={'pk': prop.pk})
    query_params = '?action=send'
    response = admin_client.get(url + query_params, follow=True)
    reverse('sapl.materia:proposicao-confirmar',
                                kwargs={
                                    'hash': prop.hash_code.split(SEPARADOR_HASH_PROPOSICAO)[0][1:],
                                    'pk': prop.pk})
    results = {
            'messages': {
                'success': ['Proposição incorporada com sucesso']
            },
            'url': reverse('sapl.materia:receber-proposicao')
        }

    ano = 2019
    tipo = prop.tipo.tipo_conteudo_related
    criar_materias(ano, tipo)
    #TODO: Testes para cada tipo de numeracao
    if numeracao == 'A':
        numero = MateriaLegislativa.objects.filter(
                    ano=ano, tipo=tipo).aggregate(Max('numero'))
        assert numero['numero__max'] == 10
#     elif numeracao == 'L':
#         legislatura = Legislatura.objects.filter(
#                 data_inicio__year__lte=ano,
#                 data_fim__year__gte=ano).first()
#         data_inicio = legislatura.data_inicio
#         data_fim = legislatura.data_fim
#         numero = MateriaLegislativa.objects.filter(
#                 data_apresentacao__gte=data_inicio,
#                 data_apresentacao__lte=data_fim,
#                 tipo=tipo).aggregate(
#                 Max('numero'))
#     elif numeracao == 'U':
#         numero = MateriaLegislativa.objects.filter(
#                 tipo=tipo).aggregate(Max('numero'))
    if numeracao is None:
        numero = {}
        numero['numero__max'] = 0
    
    #TODO: Testes para um numero_materia_futuro definido
    numero_materia_futuro = None
    if numero_materia_futuro and not MateriaLegislativa.objects.filter(tipo=tipo,
                                                                        ano=ano,
                                                                        numero=numero_materia_futuro):
        max_numero = numero_materia_futuro
    else:
        max_numero = numero['numero__max'] + \
                1 if numero['numero__max'] else 1
    
    data_teste = datetime.datetime(2019, 4, 29, 14, 54, 51)
    regime_tramitacao = mommy.make(RegimeTramitacao, descricao='Teste_Regime')

    # dados básicos
    materia = mommy.make(MateriaLegislativa, numero=max_numero, tipo=tipo, ementa=prop.descricao,
                ano=ano, data_apresentacao=data_teste, em_tramitacao=True,
                regime_tramitacao = regime_tramitacao)

    if prop.texto_original:
        arq = File(
                prop.texto_original,
                os.path.basename(prop.texto_original.path))
        materia.texto_original = arq

    #TODO: Testes para texto articulado
#     if prop.texto_articulado.exists():
#         ta = prop.texto_articulado.first()
#         ta_materia = ta.clone_for(materia)
#         ta_materia.editing_locked = True
#         ta_materia.privacidade = STATUS_TA_IMMUTABLE_PUBLIC
#         ta_materia.save()

    results['messages']['success'].append(_(
        'Matéria Legislativa registrada com sucesso.'))

    # autoria
    autoria = mommy.make(Autoria, autor=prop.autor, materia=materia, primeiro_autor=True)

    results['messages']['success'].append(_(
        'Autoria registrada com sucesso'))

    mat_vinc = mommy.make(MateriaLegislativa,
                tipo=tipo,
                ano=ano,
                numero=4
                )

    prop.materia_de_vinculo = mat_vinc
    # Testar matéria de vinculo
    anexada = mommy.make(Anexada, materia_principal=prop.materia_de_vinculo, 
                        materia_anexada=materia, data_anexacao=data_teste)

    results['messages']['success'].append(_('Matéria anexada com sucesso'))
    
    return results


@pytest.mark.django_db(transaction=False)
def test_tramitacoes_materias_anexadas(admin_client):
    tipo_materia = mommy.make(
            TipoMateriaLegislativa,
            descricao="Tipo_Teste"
    )
    materia_principal = mommy.make(
            MateriaLegislativa,
            ano=2018,
            data_apresentacao="2018-01-04",
            tipo=tipo_materia
    )
    materia_anexada = mommy.make(
            MateriaLegislativa,
            ano=2019,
            data_apresentacao="2019-05-04",
            tipo=tipo_materia
    )
    materia_anexada_anexada = mommy.make(
            MateriaLegislativa,
            ano=2020,
            data_apresentacao="2020-01-05",
            tipo=tipo_materia
    )

    mommy.make(
            Anexada,
            materia_principal=materia_principal,
            materia_anexada=materia_anexada,
            data_anexacao="2019-05-11"
    )
    mommy.make(
            Anexada,
            materia_principal=materia_anexada,
            materia_anexada=materia_anexada_anexada,
            data_anexacao="2020-11-05"
    )


    unidade_tramitacao_local_1 = make_unidade_tramitacao(descricao="Teste 1")
    unidade_tramitacao_destino_1 = make_unidade_tramitacao(descricao="Teste 2")
    unidade_tramitacao_destino_2 = make_unidade_tramitacao(descricao="Teste 3")

    status = mommy.make(
        StatusTramitacao,
        indicador='R')

    # Teste criação de Tramitacao
    form = TramitacaoForm(data={})
    form.data = {'data_tramitacao':date(2019, 5, 6),
                'unidade_tramitacao_local':unidade_tramitacao_local_1.pk,
                'unidade_tramitacao_destino':unidade_tramitacao_destino_1.pk,
                'status':status.pk,
                'urgente': False,
                'texto': "Texto de teste"}
    form.instance.materia_id=materia_principal.pk

    assert form.is_valid()

    tramitacao_principal = form.save()
    tramitacao_anexada = materia_anexada.tramitacao_set.last()
    tramitacao_anexada_anexada = materia_anexada_anexada.tramitacao_set.last()

    # Verifica se foram criadas as tramitações para as matérias anexadas e anexadas às anexadas
    assert materia_principal.tramitacao_set.last() == tramitacao_principal
    assert tramitacao_principal.materia.em_tramitacao == (tramitacao_principal.status.indicador != "F")
    assert compara_tramitacoes_mat(tramitacao_principal, tramitacao_anexada)
    assert MateriaLegislativa.objects.get(id=materia_anexada.pk).em_tramitacao \
            == (tramitacao_anexada.status.indicador != "F")
    assert compara_tramitacoes_mat(tramitacao_anexada_anexada, tramitacao_principal)
    assert MateriaLegislativa.objects.get(id=materia_anexada_anexada.pk).em_tramitacao \
            == (tramitacao_anexada_anexada.status.indicador != "F")


    # Teste Edição de Tramitacao
    form = TramitacaoUpdateForm(data={})
    # Alterando unidade_tramitacao_destino
    form.data = {'data_tramitacao':tramitacao_principal.data_tramitacao,
                'unidade_tramitacao_local':tramitacao_principal.unidade_tramitacao_local.pk,
                'unidade_tramitacao_destino':unidade_tramitacao_destino_2.pk,
                'status':tramitacao_principal.status.pk,
                'urgente': tramitacao_principal.urgente,
                'texto': tramitacao_principal.texto}
    form.instance = tramitacao_principal

    assert form.is_valid()
    tramitacao_principal = form.save()
    tramitacao_anexada = materia_anexada.tramitacao_set.last()
    tramitacao_anexada_anexada = materia_anexada_anexada.tramitacao_set.last()

    assert tramitacao_principal.unidade_tramitacao_destino == unidade_tramitacao_destino_2
    assert tramitacao_anexada.unidade_tramitacao_destino == unidade_tramitacao_destino_2
    assert tramitacao_anexada_anexada.unidade_tramitacao_destino == unidade_tramitacao_destino_2


    # Teste Remoção de Tramitacao
    url = reverse('sapl.materia:tramitacao_delete', 
                    kwargs={'pk': tramitacao_principal.pk})
    response = admin_client.post(url, {'confirmar':'confirmar'} ,follow=True)
    assert Tramitacao.objects.filter(id=tramitacao_principal.pk).count() == 0
    assert Tramitacao.objects.filter(id=tramitacao_anexada.pk).count() == 0
    assert Tramitacao.objects.filter(id=tramitacao_anexada_anexada.pk).count() == 0


    # Testes para quando as tramitações das anexadas divergem
    form = TramitacaoForm(data={})
    form.data = {'data_tramitacao':date(2019, 5, 6),
                'unidade_tramitacao_local':unidade_tramitacao_local_1.pk,
                'unidade_tramitacao_destino':unidade_tramitacao_destino_1.pk,
                'status':status.pk,
                'urgente': False,
                'texto': "Texto de teste"}
    form.instance.materia_id=materia_principal.pk

    assert form.is_valid()

    tramitacao_principal = form.save()
    tramitacao_anexada = materia_anexada.tramitacao_set.last()
    tramitacao_anexada_anexada = materia_anexada_anexada.tramitacao_set.last()

    form = TramitacaoUpdateForm(data={})
    # Alterando unidade_tramitacao_destino
    form.data = {'data_tramitacao':tramitacao_anexada.data_tramitacao,
                'unidade_tramitacao_local':tramitacao_anexada.unidade_tramitacao_local.pk,
                'unidade_tramitacao_destino':unidade_tramitacao_destino_2.pk,
                'status':tramitacao_anexada.status.pk,
                'urgente': tramitacao_anexada.urgente,
                'texto': tramitacao_anexada.texto}
    form.instance = tramitacao_anexada

    assert form.is_valid()

    tramitacao_anexada = form.save()
    tramitacao_anexada_anexada = materia_anexada_anexada.tramitacao_set.last()

    assert tramitacao_principal.unidade_tramitacao_destino == unidade_tramitacao_destino_1
    assert tramitacao_anexada.unidade_tramitacao_destino == unidade_tramitacao_destino_2
    assert tramitacao_anexada_anexada.unidade_tramitacao_destino == unidade_tramitacao_destino_2

    # Editando a tramitação principal, as tramitações anexadas não devem ser editadas
    form = TramitacaoUpdateForm(data={})
    # Alterando o texto
    form.data = {'data_tramitacao':tramitacao_principal.data_tramitacao,
                'unidade_tramitacao_local':tramitacao_principal.unidade_tramitacao_local.pk,
                'unidade_tramitacao_destino':tramitacao_principal.unidade_tramitacao_destino.pk,
                'status':tramitacao_principal.status.pk,
                'urgente': tramitacao_principal.urgente,
                'texto': "Testando a alteração"}
    form.instance = tramitacao_principal

    assert form.is_valid()
    tramitacao_principal = form.save()
    tramitacao_anexada = materia_anexada.tramitacao_set.last()
    tramitacao_anexada_anexada = materia_anexada_anexada.tramitacao_set.last()

    assert tramitacao_principal.texto == "Testando a alteração"
    assert not tramitacao_anexada.texto == "Testando a alteração"
    assert not tramitacao_anexada_anexada.texto == "Testando a alteração"

    # Removendo a tramitação pricipal, as tramitações anexadas não devem ser removidas, pois divergiram
    url = reverse('sapl.materia:tramitacao_delete', 
                    kwargs={'pk': tramitacao_principal.pk})
    response = admin_client.post(url, {'confirmar':'confirmar'} ,follow=True)
    assert Tramitacao.objects.filter(id=tramitacao_principal.pk).count() == 0
    assert Tramitacao.objects.filter(id=tramitacao_anexada.pk).count() == 1
    assert Tramitacao.objects.filter(id=tramitacao_anexada_anexada.pk).count() == 1

    # Removendo a tramitação anexada, a tramitação anexada à anexada deve ser removida
    url = reverse('sapl.materia:tramitacao_delete', 
                    kwargs={'pk': tramitacao_anexada.pk})
    response = admin_client.post(url, {'confirmar':'confirmar'} ,follow=True)
    assert Tramitacao.objects.filter(id=tramitacao_anexada.pk).count() == 0
    assert Tramitacao.objects.filter(id=tramitacao_anexada_anexada.pk).count() == 0


def test_recebimento_proposicao(admin_client):
    tipo_autor = mommy.make(TipoAutor, descricao='Teste Tipo_Autor')
    user = get_user_model().objects.filter(is_active=True)[0]

    autor = mommy.make(
        Autor,
        user=user,
        tipo=tipo_autor,
        nome='Autor Teste')

    file_content = 'file_content'
    texto = SimpleUploadedFile("resources/test.pdf", file_content.encode('UTF-8'))

    mcts = ContentType.objects.get_for_models(
        *models_with_gr_for_model(TipoProposicao))

    for pk, mct in enumerate(mcts):
        tipo_conteudo_related = mommy.make(mct, pk=pk + 1)

        response = admin_client.post(
        reverse('sapl.materia:proposicao_create'),
            {'tipo': mommy.make(
                TipoProposicao, pk=3,
                tipo_conteudo_related=tipo_conteudo_related).pk,
                'descricao': 'Teste proposição',
                'justificativa_devolucao': '  ',
                'status': 'E',
                'autor': autor.pk,
                'texto_original': texto,
                'salvar': 'salvar',
                'receber_recibo': 'True',
           },
           follow=True)

        assert response.status_code == 200

        proposicao = Proposicao.objects.first()
        gerar_hash(proposicao)

        results = enviar_receber_proposicao(proposicao, admin_client)

        import ipdb; ipdb.set_trace()
        pass
