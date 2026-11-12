import os
import socket
import streamlit as st
import pandas as pd
import gspread

socket.setdefaulttimeout(60)

@st.cache_resource(show_spinner=False)
def obter_cliente_gspread():

    caminho_direto = os.path.abspath("credenciais.json")
    caminho_raiz = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "credenciais.json"))
    caminho_arquivo = caminho_direto if os.path.exists(caminho_direto) else (caminho_raiz if os.path.exists(caminho_raiz) else None)
    
    if caminho_arquivo:
        return gspread.service_account(filename=caminho_arquivo)
    
    if "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        if "private_key" in creds_dict and isinstance(creds_dict["private_key"], str):
            creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
        return gspread.service_account_from_dict(creds_dict)
    
    raise FileNotFoundError(
        "Credenciais do Google Cloud não localizadas. "
        "Certifique-se de que o arquivo 'credenciais.json' está na raiz do projeto."
    )

import time

@st.cache_data(ttl=300, show_spinner="Sincronizando dados...")
def carregar_dados(url_planilha):
    valores = None
    
    for tentativa in range(3):
        try:
            gc = obter_cliente_gspread()
            planilha = gc.open_by_url(url_planilha)
            aba = planilha.worksheet('Respostas')
            valores = aba.get_all_values()
            break
        except gspread.exceptions.WorksheetNotFound:
            st.error("Erro de Estrutura: A aba 'Respostas' não foi localizada no Google Sheets.")
            return pd.DataFrame()
        except gspread.exceptions.APIError as e:
            # Se for 503 (indisponível) ou 429 (cota), aguarda e tenta de novo
            if any(codigo in str(e) for codigo in ['503', '500', '429']) and tentativa < 2:
                time.sleep(2 * (tentativa + 1))
                continue
            st.error(f"Erro da API Google Sheets: {e}")
            return pd.DataFrame()
        except Exception as e:
            if tentativa < 2:
                time.sleep(2 * (tentativa + 1))
                continue
            st.error(f"Falha de comunicação com a base de dados: {e}")
            return pd.DataFrame()

    if not valores or len(valores) < 2:
        st.warning("A base de inspeções está vazia no momento.")
        return pd.DataFrame()
        
    df = pd.DataFrame(valores[1:], columns=valores[0])

    if 'DATA' in df.columns:
        df = df[df['DATA'].astype(str).str.strip() != ''].copy()

    s_datas = df['DATA'].astype(str).str.strip().str.split().str[0]
    
    mask_iso = s_datas.str.contains('-', regex=False)
    
    datas_convertidas = pd.Series(pd.NaT, index=df.index)
    if mask_iso.any():
        datas_convertidas.loc[mask_iso] = pd.to_datetime(s_datas[mask_iso], format='%Y-%m-%d', errors='coerce')
    if (~mask_iso).any():
        datas_convertidas.loc[~mask_iso] = pd.to_datetime(s_datas[~mask_iso], format='%d/%m/%Y', errors='coerce')
        
    df['DATA_ORDEM'] = datas_convertidas
    df = df.dropna(subset=['DATA_ORDEM']).sort_values('DATA_ORDEM').reset_index(drop=True)
    df['DATA_OBJ'] = df['DATA_ORDEM'].dt.date

    if 'ACFT-LINHA' in df.columns:
        s_acft = df['ACFT-LINHA'].astype(str).str.strip()
        split_acft = s_acft.str.split(':', n=1, expand=True)
        
        matricula = split_acft[0].str.strip().str.upper()
        
        if split_acft.shape[1] >= 2:
            linha_acft = split_acft[1].fillna('').str.strip().str.capitalize()
        else:
            linha_acft = pd.Series('', index=df.index)
            
        linha_id = pd.Series('', index=df.index)
        if 'ID' in df.columns:
            s_id = df['ID'].astype(str).str.strip()
            extraido = s_id.str.extract(r':\s*([^_]+)_')
            if not extraido.empty and 0 in extraido.columns:
                linha_id = extraido[0].fillna('').str.strip().str.capitalize()
        
        linha_final = linha_acft.replace('', None).fillna(linha_id).fillna('Não Informada')
        
        df['LINHA'] = linha_final
        mask_valida = (linha_final != '') & (linha_final != 'Não Informada')
        
        df['ACFT-LINHA'] = matricula
        df.loc[mask_valida, 'ACFT-LINHA'] = matricula[mask_valida] + ": " + linha_final[mask_valida]

    def extrair_segundos(valor):
        if pd.isna(valor):
            return 0
        texto = str(valor).strip()
        if not texto or texto in ['-', '0', '00:00:00']:
            return 0
        
        if ':' in texto:
            partes = texto.split(':')
            try:
                if len(partes) == 3:
                    h, m, s = map(float, partes)
                    return int(h * 3600 + m * 60 + s)
                elif len(partes) == 2:
                    m, s = map(float, partes)
                    return int(m * 60 + s)
            except Exception:
                return 0

        try:
            num = float(texto)
            if 0 < num < 1:  # Fração de dia do Sheets (ex: 0.037685)
                return int(round(num * 86400))
            return int(num)
        except ValueError:
            return 0

    coluna_tempo = None
    for col_candidata in ['TIME TOTAL FORMATADO', 'TIME TOTAL', 'TIME TOTAL FORM', 'TEMPO TOTAL']:
        if col_candidata in df.columns:
            coluna_tempo = col_candidata
            break

    if coluna_tempo:
        df['TIME_SEGUNDOS'] = df[coluna_tempo].apply(extrair_segundos)
        seg_validos = df['TIME_SEGUNDOS'].fillna(0)
        horas = (seg_validos // 3600).astype(int)
        minutos = ((seg_validos % 3600) // 60).astype(int)
        segs = (seg_validos % 60).astype(int)
        
        tempo_fmt = minutos.astype(str) + "m " + segs.astype(str).str.zfill(2) + "s"
        mask_h = horas > 0
        
        tempo_fmt.loc[mask_h] = horas[mask_h].astype(str) + "h " + minutos[mask_h].astype(str).str.zfill(2) + "m " + segs[mask_h].astype(str).str.zfill(2) + "s"
        tempo_fmt.loc[df['TIME_SEGUNDOS'] <= 0] = "-"
        
        df['TIME_FORMATADO'] = tempo_fmt

    if 'JUSTIFICATIVA' in df.columns:
        df['JUSTIFICATIVA'] = df['JUSTIFICATIVA'].fillna('-').replace({'': '-', 'None': '-', 'nan': '-'})

    if 'REGISTRO FOTOS' in df.columns:
        import re

        def extrair_links(valor):
            if not valor or pd.isna(valor):
                return []
            texto = str(valor).strip()
            if texto.lower() in ['nan', 'none', '']:
                return []
            partes = [p.strip() for p in re.split(r'[,;\n]+', texto) if p.strip()]
            links = []
            for p in partes:
                match = re.search(r'lh3\.googleusercontent\.com/d/([^=?,\s|]+)', p)
                if match:
                    links.append(f"https://drive.google.com/file/d/{match.group(1)}/view")
                elif 'drive.google.com' in p or p.startswith('http'):
                    links.append(p.rstrip('|').strip())
            return links

        df['FOTOS_LISTA'] = df['REGISTRO FOTOS'].apply(extrair_links)
        df['REGISTRO_FOTOS_LINK'] = df['FOTOS_LISTA'].apply(lambda l: l[0] if len(l) > 0 else None)

    return df

@st.cache_data(ttl=300, show_spinner="Atualizando aeronaves ativas...")
def carregar_prefixos(url_planilha):
    try:
        gc = obter_cliente_gspread()
        planilha = gc.open_by_url(url_planilha)
        aba = planilha.worksheet('Prefixos')
        valores = aba.get_all_values()
        
        if not valores or len(valores) < 2:
            return pd.DataFrame(columns=['Prefixos', 'LINHA_META'])
            
        df_prefixos = pd.DataFrame(valores[1:], columns=valores[0])
        df_prefixos = df_prefixos.loc[:, df_prefixos.columns != '']
        
        if 'Prefixos' not in df_prefixos.columns:
            return pd.DataFrame(columns=['Prefixos', 'LINHA_META'])
            
        df_prefixos = df_prefixos[df_prefixos['Prefixos'].astype(str).str.strip() != '']

        split_p = df_prefixos['Prefixos'].astype(str).str.split(':', n=1, expand=True)
        if split_p.shape[1] == 2:
            df_prefixos['Prefixos'] = split_p[0].str.strip().str.upper() + ": " + split_p[1].str.strip().str.capitalize()
            df_prefixos['LINHA_META'] = split_p[1].str.strip().str.capitalize()
        else:
            df_prefixos['LINHA_META'] = None

        return df_prefixos
    except Exception:
        return pd.DataFrame(columns=['Prefixos', 'LINHA_META'])