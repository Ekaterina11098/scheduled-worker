import sys,types,unittest,os
from unittest.mock import patch
from types import SimpleNamespace as NS
sys.modules['dotenv']=NS(load_dotenv=lambda:None)
sys.modules['openai']=NS(OpenAI=None)
sys.modules['review_benchmarks']=NS(example_context=lambda *a:'',recent_benchmarks=lambda:[])
sys.modules['review_purchase_context']=NS(purchase_instructions=lambda f:'Статус: отказ. Не приглашать в чат.',purchase_status=lambda f:f.get('orderStatus'),purchase_conflicts=lambda *a:[])
import openai_client as client
class Recovery(unittest.TestCase):
 def test_double_space_customer_and_validation_retry(self):
  texts=iter([
   'Вера Лур, добрый день. Оформите возврат.\nС уважением, команда VESCHI',
   'Вера Лур, добрый день. Нам жаль, что длина манишки вам не подошла.\nС уважением, команда VESCHI',
   'Вера Лур, добрый день. Спасибо, что рассказали о посадке. Понимаем ваше разочарование: ожидания от модели не оправдались. Желаем удачных покупок.\nС уважением, команда VESCHI'])
  prompts=[]
  def create(**kw):
   prompts.append(kw['messages'][-1]['content'])
   return NS(choices=[NS(message=NS(content=next(texts)))])
  fake=NS(chat=NS(completions=NS(create=create)))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(client,'OpenAI',return_value=fake),patch.object(client,'load_system_prompt',return_value='rules'):
   out=client.generate_draft({'userName':'Вера  Лур','text':'Модель слишком короткая','orderStatus':'rejected','productValuation':3})
  self.assertTrue(out['variant1'].startswith('Вера  Лур, добрый день.'))
  self.assertIn('запрещённое слово',prompts[1])
  self.assertNotIn('чат с продавцом',out['variant1'])
 def test_question_retry_receives_validation_errors_and_keeps_two_variants(self):
  from unittest.mock import mock_open
  texts=iter([
   'Добрый день! Оформите возврат.\nС уважением, команда VESCHI',
   'Добрый день! Уточните, пожалуйста, вы уже получили товар?\nС уважением, команда VESCHI',
   'Добрый день! Оформите возврат.\nС уважением, команда VESCHI',
   'Добрый день! Чтобы подсказать порядок действий, расскажите, пожалуйста, о вашей ситуации подробнее.\nС уважением, команда VESCHI'])
  prompts=[]
  def create(**kw):
   prompts.append(kw['messages'][-1]['content'])
   return NS(choices=[NS(message=NS(content=next(texts)))])
  fake=NS(chat=NS(completions=NS(create=create)))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(client,'OpenAI',return_value=fake),patch('builtins.open',mock_open(read_data='rules')):
   out=client.generate_question_drafts({'text':'Как работает возврат товара?'})
  self.assertIn('запрещённое слово',prompts[1])
  self.assertIn('запрещённое слово',prompts[3])
  self.assertNotIn('возврат',out['variant1'])
  self.assertNotIn('возврат',out['variant2'])
  self.assertNotEqual(out['variant1'],out['variant2'])
 def test_return_question_validation_failure_still_produces_valid_manual_clarifications(self):
  from unittest.mock import mock_open
  calls=[]
  def create(**kw):
   calls.append(kw)
   return NS(choices=[NS(message=NS(content='Добрый день! Оформите возврат.\nС уважением, команда VESCHI'))])
  fake=NS(chat=NS(completions=NS(create=create)))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(client,'OpenAI',return_value=fake),patch('builtins.open',mock_open(read_data='rules')):
   out=client.generate_question_drafts({'text':'А как в данном случае работает возврат товара?'})
  self.assertEqual(len(calls),3)
  for text in (out['variant1'],out['variant2']):
   self.assertTrue(client.validate_answer(text,{'userName':'','text':'','productValuation':0})['approved'])
   self.assertIn('?',text)
   self.assertNotIn('возврат',text.lower())
   self.assertNotIn('гарантируем',text.lower())
  self.assertTrue(client._sufficiently_different(out['variant1'],out['variant2']))
 def test_unrelated_question_does_not_receive_return_clarification(self):
  from unittest.mock import mock_open
  fake=NS(chat=NS(completions=NS(create=lambda **kw:NS(choices=[NS(message=NS(content='invalid'))]))))
  with patch.dict(os.environ,{'OPENAI_API_KEY':'test'}),patch.object(client,'OpenAI',return_value=fake),patch('builtins.open',mock_open(read_data='rules')):
   with self.assertRaisesRegex(RuntimeError,'корректный ответ'):
    client.generate_question_drafts({'text':'Из чего сделаны спицы?'})
if __name__=='__main__':unittest.main()

