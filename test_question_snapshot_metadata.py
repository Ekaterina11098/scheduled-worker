import copy,unittest
from unittest.mock import Mock
from review_morning import persist_source_snapshot
class SourceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.saved=dict(kind='questions',cabinet='token_3',item_id='q',version='v',
            item=dict(id='q',text='Return?',answer=None,wasViewed=False,updatedDate='old',
                      productDetails=dict(nmId=123,supplierArticle='bag')),
            observed_at=1,source_sha256='original')
        self.store=Mock()
        self.store.read.return_value=self.saved
    def test_view_metadata_reuses_original_raw_snapshot_and_hash(self):
        fresh=copy.deepcopy(self.saved)
        fresh.update(observed_at=2,source_sha256='new')
        fresh['item'].update(wasViewed=True,updatedDate='new')
        result=persist_source_snapshot(self.store,'key',fresh,reuse_identical=True)
        self.assertIs(result,self.saved)
        self.assertEqual(result['source_sha256'],'original')
        self.assertFalse(result['item']['wasViewed'])
        self.store.insert.assert_not_called()
    def test_actual_question_changes_remain_blocked(self):
        for field,value in [('text','Different?'),('answer',{'text':'Answered'}),('productDetails',{'nmId':456}),('state','changed')]:
            with self.subTest(field=field):
                fresh=copy.deepcopy(self.saved);fresh['item'][field]=value
                with self.assertRaisesRegex(RuntimeError,'immutable'):
                    persist_source_snapshot(self.store,'key',fresh,reuse_identical=True)
        self.store.insert.assert_not_called()
    def test_feedback_metadata_remains_strict(self):
        saved=copy.deepcopy(self.saved);saved['kind']='feedbacks'
        self.store.read.return_value=saved
        fresh=copy.deepcopy(saved);fresh['item']['wasViewed']=True
        with self.assertRaises(RuntimeError):
            persist_source_snapshot(self.store,'key',fresh,reuse_identical=True)
    def test_initial_snapshot_inserted_unchanged(self):
        self.store.read.return_value=None
        self.assertIs(persist_source_snapshot(self.store,'key',self.saved,True),self.saved)
        self.store.insert.assert_called_once_with('key',self.saved)
if __name__=='__main__':unittest.main()
