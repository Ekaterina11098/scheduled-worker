import {tablePng} from './china_table_png.mjs';
import {salesChart} from './china_sales_chart.mjs';
const ROOT='china_agent:shop_conversion_ui:v1:',DATA='china_agent:shop_funnel:v1:',CHAT=-1004342917488,BOT=8780468043;
const fmt=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2});
const today=n=>new Date(n.getTime()+10800000).toISOString().slice(0,10);
const shift=(s,n)=>new Date(Date.parse(s+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
export function parsePeriod(text,now=new Date()){
 const tokens=text.trim().split(/\s+(?:—|–|-)\s+|\s+/).filter(Boolean);
 if(tokens.length!==2)throw Error('Введите две даты: 2026-11-09 2026-11-15');
 const convert=t=>/^\d{2}\.\d{2}\.\d{4}$/.test(t)?t.slice(6)+'-'+t.slice(3,5)+'-'+t.slice(0,2):t;
 const [start,end]=tokens.map(convert);
 if(![start,end].every(d=>/^\d{4}-\d{2}-\d{2}$/.test(d)&&Number.isFinite(Date.parse(d))&&new Date(d+'T00:00:00Z').toISOString().slice(0,10)===d)||start>end||end>=today(now)||(Date.parse(end)-Date.parse(start))/86400000>=31)throw Error('Нужно от1до31 завершённого дня МСК; сегодняшний день не включается.');
 return {start,end};
}
function good(r){
 return r&&[r.opens,r.carts,r.orders,r.product_count].every(v=>Number.isSafeInteger(v)&&v>=0)&&r.product_count>0;
}
const value=v=>v===null||!Number.isFinite(v)?'н/д':fmt.format(v);
export async function storeView(data,start,end,sid,mode='summary',page=0){
 if(data?.status!=='complete'||data.cabinet!=='token_3'||data.scope!=='all_sources_all_products'||data.coverage_complete!==true||data.period_from!==start||data.period_to!==end||!['selected','previous','week'].every(k=>good(data[k])))throw Error('Полный проверенный срез конверсии магазина недоступен.');
 const daily=data.daily;
 if(data.version!==2||!Array.isArray(daily)||daily.length!==(Date.parse(end)-Date.parse(start))/86400000+1||!daily.every((r,i)=>r.date===shift(start,i)&&good(r)&&good(r.previous)&&good(r.week)))throw Error('Дневные данные конверсии ещё собираются.');
 const cr=r=>r.opens?100*r.orders/r.opens:null;
 const keyboard=nav(sid);keyboard.inline_keyboard.unshift([{text:'Сводка',callback_data:'csc1:'+sid+':summary'},{text:'График по дням',callback_data:'csc1:'+sid+':graph'}],[{text:'Таблица по дням',callback_data:'csc1:'+sid+':daily'}]);
 if(mode==='graph')return {photo:await salesChart(daily.map(r=>({date:r.date,count:cr(r),amount_cny:r.opens?100*r.carts/r.opens:null})),['ОТКРЫТИЯ В ЗАКАЗ, %','ОТКРЫТИЯ В КОРЗИНУ, %'],{precision:2}),text:'Динамика конверсий магазина · '+start+' — '+end+'\nОбщая воронка WB, полные дни МСК. Проценты по суммам всех товаров. Подробности и обе базы сравнения — в таблице по дням.',reply_markup:keyboard};
 if(mode==='daily'){
  page=Math.max(0,Math.min(page,Math.floor((daily.length-1)/10)));
  const rows=daily.slice(page*10,page*10+10).map(r=>[r.date,value(r.opens),value(r.carts),value(r.orders),value(cr(r)),value(cr(r.previous)),value(cr(r.week))]);
  const photo=await tablePng({title:'Китай · динамика конверсий',subtitle:start+' — '+end+' · полные дни МСК · страница '+(page+1)+'/'+Math.ceil(daily.length/10),columns:[['Дата',240],['Открытия',200],['Корзины',190],['Заказы',190],['CR,%',200],['CR днём\nранее,%',230],['CR неделей\nранее,%',250]].map(([label,width])=>({label,width})),rows,footnotes:['CR = суммарные заказы / суммарные открытия × 100%. Общая воронка WB, все источники.','Обе базы — такие же полные дни МСК. н/д — нулевой знаменатель, не 0%.','Открытия не уникальные посетители, заказы не выкупы. WB может запаздывать до 2 часов.']});
  if(daily.length>10)keyboard.inline_keyboard.unshift([{text:'‹ Предыдущая',callback_data:'csc1:'+sid+':prev'},{text:'Следующая ›',callback_data:'csc1:'+sid+':next'}]);
  return {photo,text:'Конверсии магазина по дням · '+start+' — '+end,reply_markup:keyboard};
 }
 const rows=[['selected','Выбранный период'],['previous','На день ранее'],['week','Неделей ранее']].map(([k,label])=>{
  const r=data[k],a=r.opens?100*r.carts/r.opens:null,b=r.carts?100*r.orders/r.carts:null,c=r.opens?100*r.orders/r.opens:null;
  return [label+'\n'+r.period_from+' — '+r.period_to,value(r.opens),value(r.carts),value(a),value(r.orders),value(b),value(c)];
 });
 const photo=await tablePng({title:'Китай · конверсии магазина',subtitle:start+' — '+end+' · полные дни МСК · общая воронка WB',columns:[['Период',460],['Открытия',190],['Корзины',180],['В корзину,%',230],['Заказы',170],['Из корзины\nв заказ,%',250],['Открытия\nв заказ,%',250]].map(([label,width])=>({label,width})),rows,footnotes:['Все товары ответа WB, все источники трафика; полнота страниц проверена. Не складывается с рекламной воронкой.','Проценты — отношение суммарных счётчиков, не среднее процентов товаров. Открытия — не уникальные посетители.','Отношение заказов к корзинам не доказывает переход одной и той же когорты покупателей; заказы — не выкупы.','При нулевом знаменателе — н/д. WB может запаздывать до2часов.']});
 const times=data.source_observed_at||['selected','previous','week'].map(k=>data[k].observed_at);
 const msk=t=>new Date(t).toLocaleString('ru-RU',{timeZone:'Europe/Moscow'});
 return {photo,text:'Конверсии магазина · '+start+' — '+end+'\nВсе источники общей воронки WB. До '+data.selected.product_count+' карточек в дневном ответе.\nДатированные источники: '+msk(times[0])+' — '+msk(times.at(-1))+' МСК.',reply_markup:keyboard};
}
function nav(sid){return {inline_keyboard:[[{text:'Изменить период',callback_data:'csc1:'+sid+':period'}],[{text:'Найти товар',callback_data:'cmn1:shopproduct'}],[{text:'‹ Продажи',callback_data:'cmn1:sales'}],[{text:'Главное меню',callback_data:'cmn1:home'}]]};}
export async function handleStoreConversions(config,update,deps){
 const cb=update.callback_query,m=cb?.message||update.message,actor=cb?.from||m?.from;
 const initial=cb?.data==='cmn1:shopconv',match=/^csc1:([a-f0-9]{16}):(period|custom|range1|range7|range14|range30|show|summary|daily|graph|next|prev)$/.exec(cb?.data||'');
 const text=update.message?.text?.trim(),possibleReply=!cb&&typeof text==='string'&&text.length<=70&&m?.reply_to_message?.from?.id===BOT;
 if(!initial&&!match&&!possibleReply)return null;
 if(config.active!==true||config.chat_id!==CHAT||config.bot_id!==BOT||m?.chat?.id!==CHAT||!['group','supergroup'].includes(m.chat.type)||!Number.isSafeInteger(update.update_id)||update.update_id<0||!Number.isSafeInteger(actor?.id)||actor.id<=0||actor.is_bot!==false||m.sender_chat||m.forward_origin||(cb&&m.from?.id!==BOT))return new Response('OK');
 const get=async k=>(await deps.database('telegram_api_cache?cache_key=eq.'+encodeURIComponent(k)+'&select=payload&limit=1'))?.[0]?.payload;
 const insert=async(k,v)=>!!(await deps.database('telegram_api_cache?on_conflict=cache_key','POST',{cache_key:k,payload:v,expires_at:'2036-11-16T00:00:00Z'},'resolution=ignore-duplicates,return=representation'))?.length;
 const put=async(k,v)=>{if((await deps.database('telegram_api_cache?cache_key=eq.'+encodeURIComponent(k),'PATCH',{payload:v},'return=representation'))?.length!==1)throw Error('Store conversion state readback failed');};
 const pending=possibleReply?await get(ROOT+'input:'+actor.id):null;
 if(!initial&&!match&&pending?.message_id!==m.reply_to_message?.message_id)return null;
 if((await get('china_agent:main_menu:v1:policy'))?.enabled!==true)return null;
 const member=await deps.telegram('getChatMember',{chat_id:CHAT,user_id:actor.id});
 if(member?.user?.id!==actor.id||member.user.is_bot!==false||!(['creator','administrator','member'].includes(member.status)||(member.status==='restricted'&&member.is_member===true)))return new Response('OK');
 const now=deps.now?deps.now():new Date(),answer=t=>cb?Response.json({method:'answerCallbackQuery',callback_query_id:cb.id,...(t?{text:t,show_alert:true}:{})}):new Response('OK');
 const dk=ROOT+'delivery:'+update.update_id;if(await get(dk))return answer('');
 let ctx={view:'period'};
 if(match){
  const old=await get(ROOT+'session:'+match[1]);
  if(!old||old.actor!==actor.id||old.message_id!==m.message_id||Date.parse(old.expires_at)<=now.getTime())return answer('Откройте «Конверсии магазина» заново.');
  ctx={...old.context};const op=match[2];
  if(op==='period'||op==='custom')ctx.view=op;
  else if(op.startsWith('range')){const n=Number(op.slice(5));ctx={view:'report',start:shift(today(now),-n),end:shift(today(now),-1)};}
  else {ctx.view='report';if(['summary','daily','graph'].includes(op)){ctx.mode=op;ctx.page=0;}if(op==='next')ctx.page=Math.min(3,(ctx.page||0)+1);if(op==='prev')ctx.page=Math.max(0,(ctx.page||0)-1);}
 }else if(possibleReply&&pending?.message_id===m.reply_to_message.message_id){
  if(Date.parse(pending.expires_at)<=now.getTime())return new Response('OK');
  try{ctx={view:'report',...parsePeriod(text,now)};}catch(e){ctx={view:'custom',error:e.message};}
 }
 const sid=[...crypto.getRandomValues(new Uint8Array(8))].map(x=>x.toString(16).padStart(2,'0')).join('');
 const b=(text,op)=>({text,callback_data:'csc1:'+sid+':'+op});
 let view;
 if(ctx.view==='period')view={text:'Конверсии магазина\nОбщая воронка всех товаров: открытия → корзины → заказы.\nВыберите завершённый период МСК.',reply_markup:{inline_keyboard:[[{...b('Вчера','range1')}],[b('7 полных дней','range7'),b('14 полных дней','range14')],[b('30 полных дней','range30')],[b('Выбрать даты','custom')],[{text:'‹ Продажи',callback_data:'cmn1:sales'}]]}};
 else if(ctx.view==='custom')view={text:(ctx.error?ctx.error+'\n':'')+'Ответьте на это сообщение двумя датами, например: 2026-11-09 2026-11-15. До31 завершённого дня МСК.',reply_markup:{force_reply:true,selective:true,input_field_placeholder:'Начало и конец периода'}};
 else{
  const data=await get(DATA+ctx.start+':'+ctx.end);
  if(data?.status==='complete'&&data.version===2)view=await storeView(data,ctx.start,ctx.end,sid,ctx.mode,ctx.page);
  else{
   const key=ROOT+'request:'+actor.id+':'+ctx.start+':'+ctx.end;let claim=await get(key);
   if(!claim){
    if(!await insert(key,{status:'requesting',created_at:now.toISOString(),wb_writes:0}))throw Error('Store funnel request claimed');
    if(typeof deps.requestAnalysis!=='function')throw Error('Store funnel collection unavailable');
    const r=await deps.requestAnalysis('Конверсии магазина · запрос меню: '+ctx.start+' '+ctx.end,update);
    if(r?.status!==200)throw Error('Store funnel collection not accepted');
    const jobs=await deps.database('business_agent_jobs?agent_id=eq.china&update_id=eq.'+update.update_id+'&chat_id=eq.'+CHAT+'&sender_id=eq.'+actor.id+'&select=id,status&limit=1');
    if(jobs?.length!==1)throw Error('Exact store funnel job missing');
    claim={status:'accepted',job_id:jobs[0].id,created_at:now.toISOString(),wb_writes:0};await put(key,claim);
   }
   view={text:'Конверсии магазина · '+ctx.start+' — '+ctx.end+'\nСбор сохранён · №'+(claim.job_id||'уточняется')+'. Готовая таблица PNG будет отдельным ответом после проверки всех страниц WB. Сейчас результат ещё не доставлен.',reply_markup:{inline_keyboard:[[b('Показать готовый PNG','show')],...nav(sid).inline_keyboard]}};
  }
 }
 if(!await insert(ROOT+'session:'+sid,{actor:actor.id,context:ctx,expires_at:new Date(now.getTime()+86400000).toISOString()}))throw Error('Session claimed');
 if(!await insert(dk,{status:'sending',actor:actor.id,wb_writes:0}))return answer('');
 let receipt;
 try{
  const base={chat_id:CHAT,reply_markup:view.reply_markup};
  if(view.photo)receipt=await deps.telegram(cb?'editMessageMedia':'sendPhoto',{...base,...(cb?{message_id:m.message_id,media:{type:'photo',media:'attach://chart',caption:view.text}}:{caption:view.text}),photo_bytes:view.photo});
  else if(cb&&!m.photo&&ctx.view!=='custom')receipt=await deps.telegram('editMessageText',{...base,message_id:m.message_id,text:view.text});
  else receipt=await deps.telegram('sendMessage',{...base,text:view.text});
  if(receipt?.chat?.id!==CHAT||receipt.from?.id!==BOT||!Number.isSafeInteger(receipt.message_id))throw Error('Store conversion receipt mismatch');
 }catch(e){await put(dk,{status:'uncertain',actor:actor.id,wb_writes:0});throw e;}
 await put(ROOT+'session:'+sid,{actor:actor.id,context:ctx,message_id:receipt.message_id,expires_at:new Date(now.getTime()+86400000).toISOString()});
 await put(dk,{status:'sent',actor:actor.id,message_id:receipt.message_id,receipt,wb_writes:0});
 if(ctx.view==='custom'){
  const k=ROOT+'input:'+actor.id,v={message_id:receipt.message_id,context:ctx,expires_at:new Date(now.getTime()+900000).toISOString()};
  if(await get(k))await put(k,v);else await insert(k,v);
 }
 if(cb&&m.photo&&!view.photo)await deps.telegram('editMessageReplyMarkup',{chat_id:CHAT,message_id:m.message_id,reply_markup:{inline_keyboard:[]}});
 return answer('');
}

