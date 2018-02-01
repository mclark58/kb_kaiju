# -*- coding: utf-8 -*-
import unittest
import os  # noqa: F401
import json  # noqa: F401
import time
import requests
import shutil
import gzip

from os import environ
try:
    from ConfigParser import ConfigParser  # py2
except:
    from configparser import ConfigParser  # py3

from pprint import pprint  # noqa: F401

from Workspace.WorkspaceClient import Workspace as workspaceService
from SetAPI.SetAPIServiceClient import SetAPI
from ReadsUtils.ReadsUtilsClient import ReadsUtils

from kb_kaiju.kb_kaijuImpl import kb_kaiju
from kb_kaiju.kb_kaijuServer import MethodContext
from kb_kaiju.authclient import KBaseAuth as _KBaseAuth

from kb_kaiju.Utils.KaijuUtil import KaijuUtil
from kb_kaiju.Utils.DataStagingUtils import DataStagingUtils
from kb_kaiju.Utils.OutputBuilder import OutputBuilder


class kb_kaijuTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        token = environ.get('KB_AUTH_TOKEN', None)
        config_file = environ.get('KB_DEPLOYMENT_CONFIG', None)
        cls.cfg = {}
        config = ConfigParser()
        config.read(config_file)
        for nameval in config.items('kb_kaiju'):
            cls.cfg[nameval[0]] = nameval[1]
        # Getting username from Auth profile for token
        authServiceUrl = cls.cfg['auth-service-url']
        auth_client = _KBaseAuth(authServiceUrl)
        user_id = auth_client.get_user(token)
        # WARNING: don't call any logging methods on the context object,
        # it'll result in a NoneType error
        cls.ctx = MethodContext(None)
        cls.ctx.update({'token': token,
                        'user_id': user_id,
                        'provenance': [
                            {'service': 'kb_kaiju',
                             'method': 'please_never_use_it_in_production',
                             'method_params': []
                             }],
                        'authenticated': 1})
        cls.wsURL = cls.cfg['workspace-url']
        cls.wsClient = workspaceService(cls.wsURL)
        cls.serviceImpl = kb_kaiju(cls.cfg)
        cls.scratch = cls.cfg['scratch']
        cls.callback_url = os.environ['SDK_CALLBACK_URL']

        suffix = int(time.time() * 1000)
        cls.wsName = "test_kb_kaiju_" + str(suffix)
        cls.ws_info = cls.wsClient.create_workspace({'workspace': cls.wsName})

        cls.kaiju_runner = KaijuUtil(cls.cfg, cls.ctx)
        cls.ru = ReadsUtils(os.environ['SDK_CALLBACK_URL'])
        cls.setAPI = SetAPI(url=cls.cfg['srv-wiz-url'], token=cls.ctx['token'])

        # prepare WS data
        cls.prepare_data()


    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, 'wsName'):
            cls.wsClient.delete_workspace({'workspace': cls.wsName})
            print('Test workspace was deleted')

    def getWsClient(self):
        return self.__class__.wsClient

    def getWsName(self):
        if hasattr(self.__class__, 'wsName'):
            return self.__class__.wsName
        suffix = int(time.time() * 1000)
        wsName = "test_kb_kaiju_" + str(suffix)
        ret = self.getWsClient().create_workspace({'workspace': wsName})  # noqa
        self.__class__.wsName = wsName
        return wsName

    def getImpl(self):
        return self.__class__.serviceImpl

    def getContext(self):
        return self.__class__.ctx


    @classmethod
    def prepare_data(cls):
        test_directory_name = 'test_kb_kaiju'
        cls.test_directory_path = os.path.join(cls.scratch, test_directory_name)
        os.makedirs(cls.test_directory_path)

        [OBJID_I, NAME_I, TYPE_I, SAVE_DATE_I, VERSION_I, SAVED_BY_I, WSID_I, WORKSPACE_I, CHSUM_I, SIZE_I, META_I] = range(11)  # object_info tuple

        # upload sequences
        basename = 'seven_species_nonuniform_10K.PE_reads_'
        fwd_filename = basename+'fwd-0.FASTQ'
        rev_filename = basename+'rev-0.FASTQ'
        reads_objname = 'seven_species_nonuniform_test1.PElib'
        #shutil.copy(os.path.join("data", fwd_filename), fwd_fastq_file_path)
        #shutil.copy(os.path.join("data", rev_filename), rev_fastq_file_path)

        # unzip and put where ReadsUtils can see them (only sees shared scratch)
        fwd_fastq_file_path = os.path.join(cls.scratch, fwd_filename)
        rev_fastq_file_path = os.path.join(cls.scratch, rev_filename)
        with gzip.open(os.path.join("data", fwd_filename+'.gz'), 'rb') as f_in, open(fwd_fastq_file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        with gzip.open(os.path.join("data", rev_filename+'.gz'), 'rb') as f_in, open(rev_fastq_file_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

        read_upload_params = {'fwd_file': fwd_fastq_file_path,
                              'rev_file': rev_fastq_file_path,
                              'sequencing_tech': 'artificial reads',
                              'interleaved': 0,
                              'wsname': cls.ws_info[1],
                              'name': reads_objname
                          }
        cls.reads_ref1 = cls.ru.upload_reads(read_upload_params)['obj_ref']
        pprint('Saved PE Lib Reads: ' + cls.reads_ref1)


    # NOTE: According to Python unittest naming rules test method names should start from 'test'. # noqa


    ### Test 1: single PE lib object
    #
    # Uncomment to skip this test
    #HIDE @unittest.skip("skipped test_1_kaiju_PE_lib")
    def test_1_kaiju_PE_lib(self):
        method_name = 'test_1_kaiju_PE_lib'
        print ("\n"+('='*(10+len(method_name))))
        print ("RUNNING "+method_name+"()")
        print (('='*(10+len(method_name)))+"\n")

        # run checkM lineage_wf app on a single assembly
        input_ref = self.reads_ref1
        output_biom_name = 'test_kb_kaiju_test1.BIOM'
        params = {
            'workspace_name':            self.ws_info[1],
            'input_refs':                [input_ref],
            'output_biom_name':          output_biom_name,
            'tax_levels':                ['phylum','genus'],
            'db_type':                   'kaiju_index',
            'filter_percent':            1,
            'subsample_percent':         10,
            'subsample_replicates':      3,
            'subsample_seed':            1,
            'seg_filter':                1,
            'min_match_length':          11,
            'greedy_run_mode':           1,
            'greedy_allowed_mismatches': 5,
            'greedy_min_match_score':    75,
            'greedy_max_e_value':        0.05,
            'filter_unclassified':       1,
            'full_tax_path':             0,
            'sort_taxa_by':              'totals'
        }
        result = self.getImpl().run_kaiju(self.getContext(), params)[0]

        pprint('End to end test result:')
        pprint(result)

        self.assertIn('report_name', result)
        self.assertIn('report_ref', result)

        # make sure the report was created and includes the HTML report and download links
        #rep = self.getWsClient().get_objects2({'objects': [{'ref': result['report_ref']}]})['data'][0]['data']
        #self.assertEquals(rep['direct_html_link_index'], 0)
        #self.assertEquals(len(rep['file_links']), 2)
        #self.assertEquals(len(rep['html_links']), 1)
        #self.assertEquals(rep['html_links'][0]['name'], 'report.html')
        pass
