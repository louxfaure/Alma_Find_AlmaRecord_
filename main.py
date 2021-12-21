#!/usr/bin/python3
# -*- coding: utf-8 -*- 
import json
import os
import logging
import logs
import AlmaSru
import re
from unidecode import unidecode

SERVICE = "Alma_SudocRecord_To_Alma_Record"
ILN = '497'
INSTANCE = 'Prod'
INSTITUTION = 'UB'
FILE_IN = '/home/loux/Téléchargements/UB_Analyse_NoticesElec_SUDOC(2).txt'
FILE_OUT = '/media/sf_LouxBox/Collection_Electroniques_UB.txt'
LIST_ERROR_ADM = []

#On initialise le logger
logs.init_logs(os.getenv('LOGS_PATH'),SERVICE,'DEBUG')
logger = logging.getLogger(SERVICE)

# Table de mapping
##Champs ou trouver les identifiants en fonction du type de document
id_fields = { 
    'lm' : {
        'elec' : '010$a',
        'print' : '452$y'
    },
    'ls' : {
        'elec' : '011$a',
        'print' : '452$x'
    },
    'li' : {
        'elec' : '011$a',
        'print' : '452$x'
    }}
##Index à utiliser en fonction du type de document
id_index = {
    'lm' : 'alma.isbn',
    'ls' : 'alma.issn',
    'li' : 'alma.issn'
}
def set_ids_bib_list(sr) :

    try : 
        elec = sr[id_fields[sr['DOC_TYPE']]['elec']].split(";")
    except AttributeError :
        elec = []
    try :
        paper = sr[id_fields[sr['DOC_TYPE']]['print']].split(";")
    except AttributeError :
        paper = []
    return {
            'elec': elec,
            'print': paper,
        }


def nettoie_titre(titre) :
    """Supprime les espace, la ponctuation et les diacritiques

    Args:
        titre (string): une chaîne de caractère
    """
    
    out = re.sub(r'[^\w]','',unidecode(titre))
    return out.lower()

def teste_titre(titre_sudoc,titre_alma):
    logger.debug('{}={}'.format(titre_sudoc,titre_alma))
    logger.debug('{}={}'.format(nettoie_titre(titre_sudoc),nettoie_titre(titre_alma)))
    if nettoie_titre(titre_sudoc) == nettoie_titre(titre_alma) :
        return True
    else :
        return False

def teste_date_pub(champ100_sudoc,date_pub_alma):
    # si Type de date de pub = reproduction on confronte la date de pub Alma à al date de pub. originale et à la date de reproduction
    if champ100_sudoc[8:9] == 'e' :
        if date_pub_alma in (champ100_sudoc[9:13],champ100_sudoc[13:17]) :
            return True
        else : 
            return False
    else :
        if champ100_sudoc[9:13] == date_pub_alma :
            return True
        else :
            return False

def teste_ppn(ppn_sudoc,ppn_alma):
    if ppn_sudoc == ppn_alma[5:]:
        return True
    else : 
        return False


def search_in_alma(ids_bib_list,sr) :
    logger.debug(ids_bib_list)
    if ids_bib_list is None :
        return False
    for id_bib in ids_bib_list :
        logger.debug("-->{}".format(id_bib))
        result = AlmaSru.AlmaSru(id_bib,id_index[sr['DOC_TYPE']],institution=INSTITUTION,service=SERVICE,instance=INSTANCE)
        if result.status == False :
            return False
        if result.nb_result == 0 :
            return False
        else :
            sr['ID_MATCH'] = id_bib
            matching_results_list = result.get_datas()
            sr['ID_NB_MATCH'] = result.nb_result
            # Analyse de la qualité du matching 
            for matching_result in matching_results_list :
                matching_result['MATCHING_SCORE'] = 0
                if sr['DOC_TYPE'] in ('ls','li') and sr['530$a'] != None and matching_result['titre_clef'] != None :
                    matching_result['MATCH_TITRE'] = teste_titre(sr['530$a'],matching_result['titre_clef'])
                else :
                    matching_result['MATCH_TITRE'] = teste_titre(sr['200$a'],matching_result['titre'])
                if matching_result['MATCH_TITRE'] :
                    matching_result['MATCHING_SCORE'] += 20
                matching_result['MATCH_DATE_PUB'] = teste_date_pub(sr['100$a'],matching_result['date_pub'])
                if matching_result['MATCH_DATE_PUB'] :
                    matching_result['MATCHING_SCORE'] += 20     
                if matching_result['ppn'] != None :
                    matching_result['MATCH_PPN'] = teste_ppn(sr['001'],matching_result['ppn'])
                    if matching_result['MATCH_PPN'] :
                        matching_result['MATCHING_SCORE'] += 20
                else :
                    matching_result['MATCH_PPN'] = None
                    matching_result['MATCHING_SCORE'] += 10
            sr['MATCHING_INFOS'] = matching_results_list
            # logger.debug(json.dumps(matching_results_list, indent=4))  
            
            return True
    return False


f_in = open(FILE_IN)
data = json.load(f_in)
for sr in data['rows']:
    sr['ERREUR'] = False
    sr['ERREUR_MSG'] = None
    sr['ID_MATCH'] = None
    sr['ID_NB_MATCH'] = 0
    sr['MATCHING_INFOS'] = []
    logger.debug(sr['001'])
    sr['DOC_TYPE'] = sr['000'][6:8]
    #Teste le Label afin de voir si on est localisé sous une notice de doc. imprimé
    if sr['DOC_TYPE'] not in ('li','lm','ls'):
        sr['ERREUR'] = True
        sr['ERREUR_MSG'] = "Mauvais code de type de document (Labels pos 6/8) : {}".format(sr['000'][6:8])
        continue
    ids_bib_list = set_ids_bib_list(sr)
    if search_in_alma(ids_bib_list['elec'],sr) == False :
        search_in_alma(ids_bib_list['print'],sr)
 
f_in.close()
# logger.debug(json.dumps(data, indent=4))
with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)



    