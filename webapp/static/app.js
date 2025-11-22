async function postJson(url, data){
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  return res.json();
}

function extractCanonicalFrom(lesson_text, lesson_html){
  try{
    if(lesson_text){
      let m = lesson_text.match(/(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*(?:<<([^>]+)>>|"?([^\n"]+)"?)/i);
      if(m) return (m[1] || m[2] || '').trim();
      m = lesson_text.match(/<<([^>]+)>>/);
      if(m) return m[1].trim();
    }
    if(lesson_html){
      // strip tags and try labels
      const plain = lesson_html.replace(/<[^>]+>/g, '\n');
      let m = plain.match(/(?:Phrase to learn|Suggested colloquial phrase)\s*[:\-]?\s*([^\n]+)/i);
      if(m) return m[1].trim();
      m = lesson_html.match(/<strong>([^<]+)<\/strong>/i);
      if(m) return m[1].trim();
    }
  }catch(e){/* ignore */}
  return null;
}

async function submitSentence(){
  const sentence = document.getElementById('sentence')?.value || '';
  if(!sentence) return;
  const out = document.getElementById('corrector-output');
  out.innerHTML = '<em>Generating... please wait.</em>';

  try{
    const res = await postJson('/submit', {sentence});
    if(res.error){
      out.textContent = 'Error: ' + res.error;
      return;
    }

    // Determine lesson HTML/text to display (prefer teaching.lesson_html, then lesson_html, then lesson_text, then teaching.lesson)
    let lessonHtml = null;
    let lessonText = null;
    if(res.teaching && res.teaching.lesson_html) lessonHtml = res.teaching.lesson_html;
    if(!lessonHtml && res.lesson_html) lessonHtml = res.lesson_html;
    if(!lessonHtml && res.lesson_text) lessonText = res.lesson_text;
    if(!lessonHtml && res.teaching && res.teaching.lesson) lessonText = res.teaching.lesson;

    if(lessonHtml){
      out.innerHTML = lessonHtml;
    } else if(lessonText){
      out.innerText = lessonText;
    } else if(res.corrector_output_html){
      out.innerHTML = res.corrector_output_html;
    } else {
      out.innerText = res.corrector_output || JSON.stringify(res);
    }

    // Determine canonical phrase to show in notification
    // Prefer the phrase extracted from the actual lesson shown to the user
    let canon = extractCanonicalFrom(lessonText || '', lessonHtml || '') || (res.teaching && res.teaching.phrase) || '';

    if(res.teaching || lessonHtml || lessonText){
      alert('Taught phrase: ' + canon);
    }

    // Refresh memory list if present
    await loadMemory();
  }catch(e){
    document.getElementById('corrector-output').textContent = 'Network error';
  }
}

async function loadMemory(){
  try{
    const data = await fetch('/review_list').then(r=>r.json());
    const listEl = document.getElementById('memory-list');
    const countEl = document.getElementById('memory-count');
    // data may be an array or an object; normalize
    let arr = Array.isArray(data) ? data : (data.results || []);
    // sort by date_added descending if present
    arr = arr.sort((a,b)=>{
      const da = a.date_added || '';
      const db = b.date_added || '';
      return db.localeCompare(da);
    });
    if(listEl){
      listEl.innerHTML = '';
      arr.forEach((m, i)=>{
        const li = document.createElement('li');
        let dateInfo = m.date_added ? (` <span class="date">(${m.date_added})</span>`) : '';
        let html = `<strong>${i+1}. ${m.phrase || ''}</strong>${dateInfo} — ${m.definition || m.meaning || ''}`;
        if(m.examples && m.examples.length){
          html += '<br><em>Examples:</em>';
          m.examples.forEach(e=> html += `<div>${e}</div>`);
        }
        // remove full lesson display to keep review compact
        li.innerHTML = html;
        listEl.appendChild(li);
      });
    }
    if(countEl) countEl.innerText = arr.length || 0;
  }catch(e){
    // ignore
  }
}

// Wire UI
document.addEventListener('DOMContentLoaded', function(){
  const submitBtn = document.getElementById('submit');
  if(submitBtn) submitBtn.addEventListener('click', submitSentence);
  // quiz area handler (keep existing behavior)
  const quizArea = document.getElementById('quiz-area');
  const quizContent = document.getElementById('quiz-content');
  const startBtn = document.getElementById('start-quiz');
  if(quizArea && startBtn){
    startBtn.addEventListener('click', async ()=>{
      // fetch a single multiple-choice question
      const q = await fetch('/quiz_mc').then(r=>r.json());
      const quiz = q || null;
      if(quiz && !quiz.error){
        // render question with radio buttons
        const choicesHtml = (quiz.choices || []).map((c,i)=> `<div><label><input type="radio" name="mc" value="${encodeURIComponent(c)}"> ${c}</label></div>`).join('');
        quizContent.innerHTML = `
          <div class="quiz-question">${quiz.question}</div>
          <form id="mc-form">${choicesHtml}</form>
          <button id="submit-mc">Submit</button>
          <div id="quiz-feedback"></div>
        `;
        document.getElementById('submit-mc').onclick = async ()=>{
          const form = document.getElementById('mc-form');
          const sel = form.querySelector('input[name="mc"]:checked');
          if(!sel){
            document.getElementById('quiz-feedback').innerText = 'Please select an answer.'; return;
          }
          const choice = decodeURIComponent(sel.value);
          // send to evaluate endpoint
          const res = await postJson('/evaluate', {phrase: quiz.phrase, answer: choice});
          const feedbackEl = document.getElementById('quiz-feedback');
          feedbackEl.innerText = (res.feedback || '') + (typeof res.score === 'number' ? (' (score: '+res.score.toFixed(2)+')') : '');
          // if incorrect, show correct answer
          if(!res.correct){
            const correct = quiz.choices && quiz.choices[quiz.correct_index] ? quiz.choices[quiz.correct_index] : null;
            if(correct){
              feedbackEl.innerText += '\nCorrect answer: ' + correct;
            }
          }
        };
      } else {
        quizContent.innerText = (quiz && quiz.error) ? quiz.error : 'No quiz available.';
      }
    });
  }

  // initial load
  loadMemory();
});

    async function renderItems(items) {
      const results = document.getElementById('results');
      results.innerHTML = '';
      if (!items || items.length === 0) { results.textContent = 'No results.'; return; }
      items.forEach((it, idx) => {
        const wrapper = document.createElement('div');
        // include date if present in the lesson_html or item
        let dateInfo = it.date_added ? ('<div class="date">' + it.date_added + '</div>') : '';
        wrapper.innerHTML = makeItemHtml(it, idx).replace('<hr>', '') + dateInfo + '<hr>';
        results.appendChild(wrapper);
      });
    }
