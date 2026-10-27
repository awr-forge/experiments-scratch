const TOKEN = process.env.TELEGRAM_TOKEN;
const GEMINI_KEY = process.env.GEMINI_KEY;
let offset = 0;
async function getUpdates() {
  try {
    const res = await fetch(`https://api.telegram.org/bot${TOKEN}/getUpdates?offset=${offset}&timeout=30`);
    const data = await res.json();
    if (data.ok && data.result.length > 0) {
      for (const update of data.result) {
        offset = update.update_id + 1;
        if (update.message && update.message.text) {
          handleMessage(update.message.chat.id, update.message.text);
        }
      }
    }
  } catch (e) { console.error('Error:', e.message); }
  setTimeout(getUpdates, 1000);
}
async function handleMessage(chatId, text) {
  try {
    await fetch(`https://api.telegram.org/bot${TOKEN}/sendChatAction`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chat_id: chatId, action: 'typing' }) });
    // نستخدم موديل جديد ومحاولة قراءة الخطأ
    const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key=${GEMINI_KEY}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ contents: [{ parts: [{ text: text }] }] }) });
    const data = await res.json();
    
    let reply = 'لم أفهم الرد.';
    if (data.error) {
      reply = `خطأ من جوجل: ${data.error.message}`;
    } else if (data.candidates && data.candidates[0].content.parts[0].text) {
      reply = data.candidates[0].content.parts[0].text;
    }
    
    await fetch(`https://api.telegram.org/bot${TOKEN}/sendMessage`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ chat_id: chatId, text: reply }) });
  } catch (e) { console.error(e); }
}
getUpdates();
