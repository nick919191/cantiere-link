/* Schermate home, cantiere e risultato. Nessun handler inline: tutto passa dai data-act in app.js (CSP). */
const FAM={
 packing_costruttore:{n:"Tabella del costruttore",c:"var(--violet)"},ddt:{n:"DDT",c:"var(--accent)"},
 certificato_31:{n:"Certificati 3.1",c:"var(--green)"},dop_costruttore:{n:"DoP del costruttore",c:"var(--teal)"},
 dop_ce_prodotto:{n:"DoP e CE di prodotto",c:"var(--orange)"},lettera_accompagnamento:{n:"Lettere",c:"#5e5ce6"},
 da_escludere:{n:"Non pertinenti",c:"var(--soft)"},illeggibile:{n:"Illeggibili",c:"var(--red)"}};
const STATI={PROVATO:"g",DEDOTTO:"b","DA CONFERMARE":"o",MANCANTE:"r"};
const COL=["PRODUTTORE","COLATA","TIPO DI ACCIAIO","CE/DoP ACCIAIERIA","CERT 3.1 ACCIAIERIA","COMMERCIANTE / CENTRO TRASF.","CE/DoP CENTRO","DDT COMMERCIANTE","COSTRUTTORE","CE/DoP COSTRUTTORE","DDT COSTRUTTORE","PARTE D'OPERA"];
const $=id=>document.getElementById(id);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const api=async(p,o)=>{const r=await fetch(p,o);const t=await r.text();let d=null;try{d=JSON.parse(t)}catch(e){}
 if(!r.ok)throw new Error(d&&typeof d.detail==="string"?d.detail:`Operazione non riuscita (HTTP ${r.status})`);
 if(d===null)throw new Error(`Risposta non valida dalla piattaforma (HTTP ${r.status})`);return d;};
let L=null,ultimoEv=0,stato=null,giaVisti=new Set(),risultatoCaricato=false,inizio=true,eraFinito=false;

function vai(id){location.hash=id?"#/"+id:"";}
window.onhashchange=route;
function route(){const m=location.hash.match(/^#\/([\w-]+)$/);
 if(m){L=m[1];$("home").classList.add("hidden");$("lavoro").classList.remove("hidden");apriLavoro()}
 else{L=null;$("lavoro").classList.add("hidden");$("home").classList.remove("hidden");$("crumb").innerHTML="";casa()}}

/* ---------- home ---------- */
let scelti=[];
const sel=$("sel"),drop=$("drop");
drop.onclick=e=>{if(!e.target.closest("[data-act]"))sel.click()};sel.onchange=()=>aggiungi([...sel.files]);
["dragenter","dragover"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add("on")}));
["dragleave","drop"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove("on")}));
drop.addEventListener("drop",ev=>aggiungi([...ev.dataTransfer.files]));
function aggiungi(f){scelti=scelti.concat(f);mostraFile()}
function mostraFile(){$("files").innerHTML=scelti.map(f=>`<div class="card file"><svg class="ic" style="color:var(--accent)"><use href="#doc"/></svg><div>${esc(f.name)}<small>${(f.size/1048576).toFixed(1)} MB</small></div></div>`).join("");
 $("send").classList.toggle("hidden",!scelti.length)}
$("annulla").onclick=()=>{scelti=[];sel.value="";mostraFile()};
$("invia").onclick=()=>{if(!scelti.length)return;const fd=new FormData();scelti.forEach(f=>fd.append("file",f));fd.append("nome",$("nome").value.trim());
 const x=new XMLHttpRequest();x.open("POST","/api/lavori");x.setRequestHeader("X-Traccia-Token",localToken);$("upbar").classList.remove("hidden");$("invia").disabled=true;$("uperr").textContent="";
 x.upload.onprogress=e=>{if(e.lengthComputable){const p=Math.round(e.loaded/e.total*100);$("upbar").firstChild.style.width=p+"%";$("uptxt").textContent=`Invio ${p}% · ${(e.loaded/1048576).toFixed(0)} di ${(e.total/1048576).toFixed(0)} MB`}};
 x.onload=()=>{$("invia").disabled=false;if(x.status===200){const r=JSON.parse(x.responseText);scelti=[];mostraFile();vai(r.lavoro)}
  else $("uperr").textContent=dettaglio(x)||`Invio non riuscito (HTTP ${x.status}). Riprova; se il problema resta, i file potrebbero essere troppo grandi.`};
 x.onerror=()=>{$("invia").disabled=false;$("uperr").textContent="La piattaforma non risponde: controlla che l’app sia aperta."};x.send(fd)};
function dettaglio(x){try{const d=JSON.parse(x.responseText).detail;return typeof d==="string"?d:""}catch(e){return ""}}
const FASI={preparazione:"Preparazione delle pagine",lettura:"Lettura in corso",composizione:"Collegamento a ritroso",pronto:"Completato",errore:"Nessuna pagina leggibile"};
function tok(n){n=Number(n)||0;return n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(n>=1e4?0:1)+"k":String(n)}
function tokens(c){if(!c||!c.chiamate)return "";return `Token ${tok(c.ingresso)} in · ${tok(c.uscita)} out · ${c.chiamate} chiamate`}
function casa(){api("/api/lavori").then(ls=>{$("lavori").innerHTML=ls.length?ls.map(l=>`<div class="card lav" data-act="open-job" data-job="${esc(l.lavoro)}"><div class="lav-head"><div class="t">${esc(l.nome)}</div><button class="btn s trash-job" data-act="confirm-trash" data-job="${esc(l.lavoro)}" aria-label="Sposta cantiere nel cestino">Elimina</button></div><div class="m">${esc(l.creato)} · ${l.pagine_totali} pagine${l.consumo&&l.consumo.chiamate?" · "+tokens(l.consumo):""}</div><div style="margin-top:8px"><span class="pill ${l.fase==="pronto"?"g":l.fase==="errore"?"r":"b"}" title="${esc(l.motivo||"")}">${FASI[l.fase]||l.fase} ${l.fase==="pronto"||l.fase==="errore"?"":"· "+l.percentuale+"%"}</span></div></div>`).join(""):`<div class="note">Nessun lavoro ancora. Carica i tuoi documenti oppure crea un cantiere di prova.</div>`}).catch(()=>{})}

/* ---------- lavoro ---------- */
function apriLavoro(){ultimoEv=0;giaVisti=new Set();risultatoCaricato=false;inizio=true;pagMostrata=null;eraFinito=false;
 $("feed").innerHTML="";$("crops").innerHTML="";$("res").classList.add("hidden");$("lavoro").classList.remove("finito");$("dettagli").open=true;togliFlyer();
 $("lookpage").innerHTML='<div class="scan"></div>';$("lookfile").textContent="In attesa delle pagine…";$("thought").textContent="Le pagine compaiono qui mentre vengono lette.";
 $("bins").innerHTML=Object.entries(FAM).map(([k,f])=>`<div class="card bin" id="bin-${k}" data-act="family" data-family="${k}"><div class="h"><div class="lab"><span class="sw" style="background:${f.c}"></span>${f.n}</div><div class="n" style="color:${f.c}">0</div></div><div class="stack"></div></div>`).join("");
 aggiorna()}  // poi è il ciclo di poll in app.js a tenerlo aggiornato
async function aggiorna(){if(!L)return;
 try{stato=await api(`/api/lavori/${L}/stato`)}catch(e){$("titolo").textContent="Lavoro non trovato";return}
 $("crumb").innerHTML=`/ <b>${esc(stato.nome)}</b>`;
 const p=stato.fase==="pronto"?100:stato.percentuale;
 $("barv").style.width=p+"%";$("ringv").style.strokeDashoffset=169.6*(1-p/100);$("ringt").textContent=p+"%";
 $("titolo").textContent={preparazione:"Preparo le pagine",lettura:"Pagine da analizzare con l’agente",composizione:"Collego a ritroso e preparo l'Excel",pronto:"Lavoro completato",errore:stato.motivo||"Nessuna pagina leggibile"}[stato.fase];
 const fatte=stato.lette+stato.non_lette.length;
 $("bart").textContent=`${fatte} di ${stato.pagine_totali} pagine · ${stato.file} file`;
 $("bare").textContent=stato.non_lette.length?`${stato.non_lette.length} pagine non lette`:"";
 $("bartok").textContent=tokens(stato.consumo);
 const ord=["preparazione","lettura","composizione","pronto"],i=ord.indexOf(stato.fase);
 $("phase").innerHTML=["Ricevuti","Preparazione","Lettura e smistamento","Collegamento a ritroso","Excel"].map((t,j)=>`<span class="${j<=i||stato.fase==="pronto"?"ok":""} ${j===i+1&&stato.fase!=="pronto"?"on":""}">${t}</span>`).join("");
 $("lookdot").style.visibility=stato.fase==="pronto"?"hidden":"visible";
 $("lookpage").classList.toggle("fermo",stato.fase==="pronto");
 // U1: a lavoro finito i risultati vengono prima; lettura e diario restano sotto, ripiegati (una volta sola, poi decide l'utente)
 const finito=stato.fase==="pronto";$("lavoro").classList.toggle("finito",finito);
 if(finito&&!eraFinito){eraFinito=true;$("dettagli").open=false;togliFlyer()}if(!finito)eraFinito=false;
 const ab=$("analyze-button");ab.classList.toggle("s",finito);ab.classList.toggle("hidden",finito&&!stato.non_lette.length);ab.textContent=finito?"Rileggi pagine mancanti":"Analizza / riprendi";
 // pagine nei contenitori
 const nuove=stato.pagine.filter(x=>x.famiglia&&!giaVisti.has(x.pid));
 nuove.forEach((x,k)=>{giaVisti.add(x.pid);if(inizio)metti(x);else setTimeout(()=>vola(x),k*180)});
 Object.keys(FAM).forEach(k=>{$("bin-"+k).querySelector(".n").textContent=stato.per_famiglia[k]||0});
 // eventi
 const ev=await api(`/api/lavori/${L}/eventi?da=${ultimoEv}`).catch(()=>[]);
 ultimoEv+=ev.length;ev.forEach(evento);
 const ultimo=ev.length?ev[ev.length-1].t:null;if(ultimo)window._ultimoT=ultimo;
 $("idle").classList.toggle("hidden",!(stato.fase==="lettura"&&window._ultimoT&&Date.now()/1000-window._ultimoT>180));
 inizio=false;
 if(stato.fase==="pronto"&&!risultatoCaricato){risultatoCaricato=true;risultato()}}
function img(pid){return `/api/lavori/${L}/miniature/${pid}.png`}
function metti(x){const st=$("bin-"+x.famiglia).querySelector(".stack");if(st.children.length<18)st.insertAdjacentHTML("beforeend",`<img src="${img(x.pid)}" alt="">`)}
function togliFlyer(){document.querySelectorAll(".flyer").forEach(f=>f.remove())}
function vola(x){if(!stato||stato.fase==="pronto"||document.hidden){metti(x);return}const bin=$("bin-"+x.famiglia),src=$("lookpage").getBoundingClientRect(),dst=bin.getBoundingClientRect();
 const el=document.createElement("img");el.className="flyer";el.src=img(x.pid);document.body.appendChild(el);
 const a=el.animate([{left:src.left+src.width/2+"px",top:src.top+src.height/3+"px",transform:"scale(3)",opacity:.95},{left:dst.left+dst.width/2+"px",top:dst.top+40+"px",transform:"scale(1)",opacity:1}],{duration:700,easing:"cubic-bezier(.3,.7,.2,1)",fill:"forwards"});
 a.onfinish=()=>{el.remove();metti(x);bin.classList.remove("flash");void bin.offsetWidth;bin.classList.add("flash")}}
const TIPI={ricevuti:["Ricevuti","n"],file:["Preparazione","n"],pagina:null,lettura:["Lettura","b"],lettura_pagina:["Sta guardando","b"],
 scheda:["Letta","g"],ritaglio:["Ritaglio","o"],nota:["Agente","b"],correzione:["Correzione","o"],errore:["Errore","r"],componi:["Collegamento","b"],pronto:["Pronto","g"]};
function evento(e){
 if(e.tipo==="lettura_pagina"&&e.pid){mostraPagina(e.pid);$("lookfile").textContent=e.testo.replace(/^\w+ guarda /,"");$("thought").innerHTML=`<b>Lettura.</b> Trascrivo la pagina e riconosco il tipo di documento…`}
 if(e.tipo==="scheda"&&e.pid){mostraPagina(e.pid,true);const f=FAM[e.famiglia];$("thought").innerHTML=`<b>${f?f.n:e.famiglia}.</b> ${esc(e.testo)}`}
 if(e.tipo==="nota"){$("thought").innerHTML=`<b>Agente.</b> ${esc(e.testo)}`}
 if(e.tipo==="ritaglio"&&e.ritaglio){$("crops").insertAdjacentHTML("afterbegin",`<img src="/api/ritagli/${encodeURIComponent(e.ritaglio)}" title="${esc(e.testo)}" data-act="open-proof" data-url="/api/ritagli/${encodeURIComponent(e.ritaglio)}" data-title="Ritaglio: ${esc(e.testo)}">`);while($("crops").children.length>4)$("crops").lastChild.remove()}
 const t=TIPI[e.tipo];if(!t)return;
 let testo=e.testo||"";if(e.tipo==="scheda"&&FAM[e.famiglia])testo=`${FAM[e.famiglia].n} · ${testo}`;
 if(e.tipo==="file")testo=`File ${e.n} di ${e.totale}: ${testo}`;
 $("feed").insertAdjacentHTML("afterbegin",`<div class="ev"><time>${esc(e.ora)}</time><span class="pill ${t[1]}">${t[0]}</span><span>${esc(testo)}</span></div>`);
 while($("feed").children.length>8)$("feed").lastChild.remove()}
let pagMostrata=null;
async function mostraPagina(pid,conZone){const box=$("lookpage");
 if(pagMostrata!==pid){pagMostrata=pid;box.innerHTML=`<img src="/api/lavori/${L}/pagine/${pid}.png" alt="pagina"><div class="scan"></div>`}
 if(!conZone)return;
 try{const d=await api(`/api/lavori/${L}/pagine/${pid}`);if(pagMostrata!==pid||!d.scheda)return;
  const zone=[];const s=d.scheda;Object.values(s.testata||{}).forEach(v=>v.v&&v.zona&&v.zona.length&&zone.push(v.zona));
  (s.timbri||[]).forEach(t=>t.zona&&t.zona.length&&zone.push(t.zona));(s.righe||[]).slice(0,6).forEach(r=>r.colata&&r.colata.zona&&r.colata.zona.length&&zone.push(r.colata.zona));
  box.querySelectorAll(".box").forEach(b=>b.remove());
  zone.slice(0,12).forEach(([x0,y0,x1,y1],k)=>setTimeout(()=>box.insertAdjacentHTML("beforeend",`<div class="box" style="left:${x0/10}%;top:${y0/10}%;width:${(x1-x0)/10}%;height:${(y1-y0)/10}%"></div>`),k*120))}catch(e){}}

/* ---------- famiglie ---------- */
function famiglia(k){if(!stato)return;const ps=stato.pagine.filter(x=>x.famiglia===k);
 $("mtitle").textContent=`${FAM[k].n} · ${ps.length} pagine`;$("mopen").classList.add("hidden");
 $("mbody").innerHTML=ps.length?`<div class="grid-pg">${ps.map(x=>`<div class="pg" data-act="page" data-pid="${esc(x.pid)}"><img src="${img(x.pid)}" alt=""><div>${esc(x.file)} · p${x.pagina}</div></div>`).join("")}</div>`:`<div class="note">Nessuna pagina in questa famiglia.</div>`;
 $("mframe").classList.add("hidden");$("mbody").classList.remove("hidden");$("modal").classList.add("on")}
async function pagina(pid){const d=await api(`/api/lavori/${L}/pagine/${pid}`);const s=d.scheda||{};
 $("mtitle").textContent=`${d.pagina.file} · pagina ${d.pagina.pagina}`;
 $("mbody").innerHTML=`<p class="sub" style="margin:0 0 12px">${esc(s.motivo||"")}</p>${(s.avvisi||[]).map(a=>`<div class="pill o" style="margin:0 6px 8px 0">${esc(a)}</div>`).join("")}<img src="/api/lavori/${L}/pagine/${pid}.png" style="width:100%;border-radius:8px;border:1px solid var(--line)">`}
function apri(url,titolo){$("mtitle").textContent=titolo;$("mopen").href=url;$("mopen").classList.remove("hidden");
 $("mframe").src=url;$("mframe").classList.remove("hidden");$("mbody").classList.add("hidden");$("modal").classList.add("on")}
function chiudi(){$("modal").classList.remove("on");$("mframe").src="about:blank"}
$("modal").onclick=e=>{if(e.target.id==="modal")chiudi()};document.onkeydown=e=>{if(e.key==="Escape")chiudi()};

/* ---------- risultato ---------- */
async function risultato(){let r;try{r=await api(`/api/lavori/${L}/risultato`)}catch(e){return}
 $("res").classList.remove("hidden");
 $("ressub").textContent=`${stato.pagine_totali} pagine da ${stato.file} file · ${r.voci.length} voci · ogni dato ha il collegamento alla pagina da cui viene.`;
 $("scarica").href=`/api/lavori/${L}/scarica`;$("riordina").href=`/api/lavori/${L}/fascicolo-ordinato`;
 $("stati").innerHTML=Object.entries(STATI).map(([k,c])=>`<div class="stato ${c}"><div class="v">${r.conteggio[k]||0}</div><div class="l">${k}</div></div>`).join("");
 const prova=(v,c)=>v.colonne[c].fonti.length?`/api/lavori/${L}/uscita/prove/v${String(v.n).padStart(3,"0")}_c${String(COL.indexOf(c)+1).padStart(2,"0")}.html`:null;
 const manca=s=>/non nel fascicolo|Non presente/i.test(s||"");
 // U4: le voci DA CONFERMARE / MANCANTI vengono prima, con i motivi, cosa manca e la domanda pronta per la chat
 const dav=r.voci.filter(v=>v.stato==="DA CONFERMARE"||v.stato==="MANCANTE");
 $("verifica-count").textContent=dav.length;$("verifica-count").className="pill "+(dav.length?"o":"g");
 $("verifica").innerHTML=dav.length?dav.map(v=>{const C=v.colonne,m=[];if(manca(C["DDT COMMERCIANTE"].v))m.push("DDT del commerciante");if(manca(C["CERT 3.1 ACCIAIERIA"].v))m.push("certificato 3.1");if(!C["COLATA"].v)m.push(v.colate_possibili.length?"colata da scegliere tra "+v.colate_possibili.join(", "):"colata");
  const domanda=`Voce ${v.n} (${v.voce}): perché è ${v.stato}? Cosa manca per provarla e cosa devo chiedere al fornitore?`;
  return `<div class="vitem"><div class="vitem-main"><div><span class="pill ${STATI[v.stato]}">${v.stato}</span> <b>${esc(v.voce)}</b> <span class="muted">${esc(v.parte_opera||"")}</span></div><div class="why-full">${esc(v.note.join(" "))}</div>${m.length?`<div class="manca"><b>Manca:</b> ${esc(m.join(", "))}</div>`:""}</div><div class="vitem-acts"><button class="btn s" data-act="goto-row" data-voice="${v.n}">Vedi i collegamenti</button><button class="btn s" data-act="ask-about" data-voice="${v.n}" data-text="${esc(domanda)}">Chiedi in chat</button></div></div>`}).join(""):`<div class="note" style="margin:0">Nessuna voce da verificare: tutte le voci sono provate o dedotte.</div>`;
 const nodo=(v,c,txt,sub,cls)=>{const u=prova(v,c);return `<div class="node ${cls||""} ${u?"click":""}" ${u?`data-act="open-proof" data-url="${u}" data-title="${esc(c)} · voce ${v.n}"`:""}>${esc(txt||"—")}<small>${esc(sub||"")}</small></div>`};
 $("chain").innerHTML=r.voci.map((v,i)=>{const C=v.colonne;const cert=C["CERT 3.1 ACCIAIERIA"].v,ddt=C["DDT COMMERCIANTE"].v,col=C["COLATA"].v;
  return `<div class="vrow" id="vrow-${v.n}" style="animation-delay:${i*60}ms"><div>${nodo(v,"PARTE D'OPERA",v.voce,v.parte_opera||"")}<button class="row-ask" data-act="select-voice" data-voice="${v.n}">Chiedi in chat ↗</button></div>
  ${nodo(v,"DDT COMMERCIANTE",ddt.replace(/^DDT n\. /,"DDT "),C["COMMERCIANTE / CENTRO TRASF."].v,manca(ddt)?"miss":"")}
  ${nodo(v,"CERT 3.1 ACCIAIERIA",cert,C["PRODUTTORE"].v,manca(cert)?"miss":(v.stato==="DA CONFERMARE"?"warn":""))}
  ${nodo(v,"COLATA",col||(v.colate_possibili.length?v.colate_possibili.length+" colate":"—"),v.colate_possibili.join(" / "),v.stato==="MANCANTE"?"miss":(!col?"warn":""))}
  <div><span class="pill ${STATI[v.stato]}">${v.stato}</span><div class="why">${esc(v.note.slice(0,2).join(" "))}</div></div></div>`}).join("");
 $("tab").innerHTML=`<tr><th>N</th>${COL.map(c=>`<th>${esc(c)}</th>`).join("")}<th>STATO</th><th>NOTE</th></tr>`+r.voci.map(v=>`<tr><td>${v.n}</td>${COL.map(c=>{const u=prova(v,c);return `<td class="${u?"src":""}" ${u?`data-act="open-proof" data-url="${u}" data-title="${esc(c)} · voce ${v.n}"`:""}>${esc(v.colonne[c].v)}</td>`}).join("")}<td><span class="pill ${STATI[v.stato]}">${v.stato}</span></td><td class="nota" style="color:var(--muted)">${esc(v.note.join(" "))}</td></tr>`).join("")}
