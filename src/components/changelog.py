import streamlit as st

VERSAO_ATUAL = "1.2.0"


@st.dialog("📢 Comunicado Operacional: Otimização de Performance")
def modal_novidades():
    st.markdown("""
    Prezados Coordenadores e Supervisores,

    Com o marco de **mais de 80 mil linhas de registros acumulados**, implementamos a utilização de dados de uma forma diferente para assegurar a velocidade e funcionamento do app.

    * 🛑 **O Gargalo Técnico do Google Sheets:** A ferramenta de planilhas do Google não foi projetada para atuar como banco de dados em larga escala. Transferir quase **1 milhão de células** pela API da Google a cada acesso gera lentidão extrema, erros de conexão e travamentos no carregamento.
    
    * Por causa disso, tivemos as seguintes mudanças:
    * ⚡ **Nova Janela Operacional (Provisório):** O painel agora foca prioritariamente no ciclo da última semana, assegurando carregamento ágil, filtros rápidos e estabilidade.
    * 💾 **Histórico Preservado:** Todas as inspeções anteriores permanecem arquivadas de forma íntegra e segura na base de dados.
    * 🚀 **Evolução Técnica:** Estamos em fase de planejamento para migração dos dados para uma infraestrutura de banco de dados corporativo dedicado, permitindo consultas históricas completas sem degradação de velocidade.

    Para suporte, dúvidas ou solicitações de relatórios consolidados, utilize o canal no menu superior (*Report a bug*).
    """)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Entendido / Acessar Dashboard", type="primary", width="stretch"):
        st.session_state["versao_novidades_vista"] = VERSAO_ATUAL
        st.query_params["v"] = VERSAO_ATUAL
        st.rerun()


def verificar_novidades():
    if st.query_params.get("v") == VERSAO_ATUAL or st.session_state.get("versao_novidades_vista") == VERSAO_ATUAL:
        return

    st.session_state["versao_novidades_vista"] = VERSAO_ATUAL
    st.query_params["v"] = VERSAO_ATUAL
    modal_novidades()