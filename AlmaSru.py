
# external imports
import requests
import xml.etree.ElementTree as ET
import logging
import urllib.parse
# internal import

ns = {'sru': 'http://www.loc.gov/zing/srw/',
        'marc': 'http://www.loc.gov/MARC21/slim' }


class AlmaSru(object):

    def __init__(self, query, index,institution ='network',service='AlmaSru',instance='Prod'):
        self.logger = logging.getLogger(service)
        self.institution = institution
        self.service = service
        self.instance = instance
        self.query = query
        self.index = index
        self.status = False
        self.result = self.sru_request()
        if  self.status == True :
            self.nb_result =self.get_nombre_resultats()
    @property

    def baseurl(self):
        if self.instance == 'Test' :
            return "https://pudb-{}-psb.alma.exlibrisgroup.com/view/sru/{}?version=1.2&operation=searchRetrieve".format(self.institution.lower(),"33PUDB_"+self.institution.upper())
        else :
            return "https://pudb-{}.alma.exlibrisgroup.com/view/sru/{}?version=1.2&operation=searchRetrieve".format(self.institution.lower(),"33PUDB_"+self.institution.upper())

    def fullurl(self, query, reponseFormat,index,noticesSuppr,complex_query):
        return self.baseurl + '&format=' + reponseFormat + '&query=' + self.searchQuery(query, index, noticesSuppr, complex_query)

    def searchQuery(self, query, index, noticesSuprr, complex_query):
        if complex_query :
            searchQuery = query
        else :
            searchQuery = index
            searchQuery += '='
            searchQuery += query
        if not noticesSuprr:
            searchQuery += ' and alma.mms_tagSuppressed=false'
        return urllib.parse.quote(searchQuery)

    def sru_request(self, reponseFormat='marcxml',noticesSuppr=False, complex_query=False):
        url=self.fullurl(self.query,reponseFormat, self.index,noticesSuppr,complex_query)
        self.logger.debug("{} :: alma_sru :: {}".format(self.query,url))
        r = requests.get(url)
        try:
            r.raise_for_status()  
        except requests.exceptions.HTTPError:
            self.status = False
            self.logger.error("{} :: {} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(self.query, 
                                                                                                            self.service ,
                                                                                                            r.status_code,
                                                                                                            r.request.method,
                                                                                                            r.url,
                                                                                                            r.text))
            self.error_msg = "{} :: {} :: HTTP Status: {} || Method: {} || URL: {} || Response: {}".format(self.query, 
                                                                                                            self.service ,
                                                                                                            r.status_code,
                                                                                                            r.request.method,
                                                                                                            r.url,
                                                                                                            r.text)
        else:
            self.status = True
            reponse = r.content.decode('utf-8')
            reponsexml = ET.fromstring(reponse)
            return reponsexml

    def get_nombre_resultats(self):
        
        if self.result.findall("sru:numberOfRecords",ns):
            return self.result.find("sru:numberOfRecords",ns).text
        else : 
            return 0
    
    def get_datas(self) :
        match_results_list = []
        nb_records = 0
        for record in self.result.findall("sru:records/sru:record",ns):
            record_id = record.find("./sru:recordIdentifier",ns).text
            # On ne sélectionne que des notices liées à des inventaires électroniques 
            if record.find(".//sru:recordData/marc:record/marc:datafield[@tag='AVE']",ns):
                # On regarde si l anotice dispose d'un PPN 
                ppn = self.get_ppn(record)
                titre = self.get_record_title(record)
                titre_clef = self.get_record_key_title(record)
                date_pub = self.get_date_pub(record)
                match_result = {
                    'mmsid' :record_id,
                    'ppn' : ppn,
                    'titre': titre,
                    'titre_clef' : titre_clef,
                    'date_pub' : date_pub,
                    'portfolios' : self.get_pf_infos(record)
                }
                self.logger.debug(match_result)
                match_results_list.append(match_result)
                nb_records += 1
        self.nb_result = nb_records
        return match_results_list

    def get_ppn(self, record):
        for other_sys_nb in record.findall(".//sru:recordData/marc:record/marc:datafield[@tag='035']",ns) :
            try :
                other_id = other_sys_nb.find("marc:subfield[@code='a']",ns).text
            except :
                # Pas de 035
                continue
            else :
                # On identifie le PPN sur la base du préfixe. On exclue les PPN erronnés qui ont un ss-champ $$9
                if other_id[:5] == "(PPN)" and other_sys_nb.find("marc:subfield[@code='9']",ns) == None :
                        return other_id
        return None


    def get_record_title(self ,record):
        return record.find(".//sru:recordData/marc:record/marc:datafield[@tag='245']/marc:subfield[@code='a']",ns).text
        
    def get_record_key_title(self ,record):
        if record.find(".//sru:recordData/marc:record/marc:datafield[@tag='222']/marc:subfield[@code='a']",ns) != None :
            return record.find(".//sru:recordData/marc:record/marc:datafield[@tag='222']/marc:subfield[@code='a']",ns).text
        else :
            return None

    def get_date_pub(self, record):
        if record.find(".//sru:recordData/marc:record/marc:controlfield[@tag='008']",ns) != None :
            date = record.find(".//sru:recordData/marc:record/marc:controlfield[@tag='008']",ns).text[7:11]
            return date


    def get_pf_infos(self,record):
        pf_list = []
        for pf in record.findall(".//sru:recordData/marc:record/marc:datafield[@tag='AVE']",ns) :
            pid = pf.find("marc:subfield[@code='8']",ns).text
            collection_id = None
            collection_name = None
            if pf.find("marc:subfield[@code='c']",ns) != None :
                collection_id = pf.find("marc:subfield[@code='c']",ns).text
            if pf.find("marc:subfield[@code='m']",ns) != None :
                collection_name = pf.find("marc:subfield[@code='m']",ns).text
            pf_datas = {
                'pid' : pid,
                'collection_id' : collection_id,
                'collection_name' : collection_name
            }
            pf_list.append(pf_datas)
        
        return pf_list