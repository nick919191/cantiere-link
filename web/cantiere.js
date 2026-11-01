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
 if(d===null)throw new Error("Risposta non valida dalla piattaforma.");return d;};
let ris=null,passoScelto=null,passoAttuale=-1,firmaOrdine="";
let L=null,ultimoEv=0,stato=null,giaVisti=new Set(),risultatoCaricato=false,inizio=true;

function vai(id){location.hash=id?"#/"+id:"";}
window.onhashchange=()=>{route();ciclo()};
function route(){const m=location.hash.match(/^#\/([\w-]+)$/);
 if(m){L=m[1];$("home").classList.add("hidden");$("lavoro").classList.remove("hidden");apriLavoro()}
 else{L=null;$("lavoro").classList.add("hidden");$("home").classList.remove("hidden");$("crumb").innerHTML="";casa()}}

/* ---------- home ---------- */
let scelti=[];
const sel=$("sel"),drop=$("drop");
drop.onclick=e=>{if(e.target!==sel)sel.click()};sel.onchange=()=>aggiungi([...sel.files]);
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
  else $("uperr").textContent=erroreUpload(x)||"Invio non riuscito. Riprova; se il problema resta, i file potrebbero essere troppo grandi."};
 x.onerror=()=>{$("invia").disabled=false;$("uperr").textContent="La piattaforma non risponde: controlla che l’app sia aperta."};x.send(fd)};
function erroreUpload(x){try{const d=JSON.parse(x.responseText).detail;return typeof d==="string"?d:""}catch(e){return ""}}
const FASI={preparazione:"Preparazione delle pagine",lettura:"Lettura in corso",composizione:"Preparazione dell'Excel",pronto:"Completato"};
function tok(n){n=Number(n)||0;return n>=1e6?(n/1e6).toFixed(1)+"M":n>=1e3?(n/1e3).toFixed(n>=1e4?0:1)+"k":String(n)}
function tokens(c){if(!c||!c.chiamate)return "";return `Token ${tok(c.ingresso)} in · ${tok(c.uscita)} out · ${c.chiamate} chiamate`}
const voci=n=>n+(n===1?" voce":" voci");
function esitoLavoro(l){const c=l.conteggio;
 if(l.fase==="errore")return [l.motivo||"Nessuna pagina leggibile","r"];
 if(l.fase!=="pronto")return [{preparazione:"Preparo le pagine",lettura:"Sto leggendo · "+l.percentuale+"%",composizione:"Preparo l'Excel"}[l.fase]||l.fase,"b"];
 const tot=c?Object.values(c).reduce((a,x)=>a+x,0):0;
 if(!tot)return ["Nessuna voce trovata","o"];
 if(c.MANCANTE)return [`Mancano documenti per ${voci(c.MANCANTE)}`,"r"];
 if(c["DA CONFERMARE"])return [`${voci(c["DA CONFERMARE"])} da confermare`,"o"];
 return [`Tutto collegato · ${tot} voci`,"g"]}
function barraConti(l){const c=l.conteggio;
 if(l.fase!=="pronto")return `<div class="conti"><i style="width:${l.fase==="preparazione"?5:l.percentuale}%;background:var(--accent)"></i></div>`;
 const tot=c?Object.values(c).reduce((a,x)=>a+x,0):0;if(!tot)return `<div class="conti"></div>`;
 return `<div class="conti">${Object.entries(STATI).map(([k,s])=>`<i style="width:${(c[k]||0)/tot*100}%;background:var(--${{g:"green",b:"accent",o:"orange",r:"red"}[s]})" title="${k}: ${c[k]||0}"></i>`).join("")}</div>`}
function casa(){api("/api/lavori").then(ls=>{$("lavori").innerHTML=ls.length?ls.map(l=>{const [e,c]=esitoLavoro(l);return `<div class="card lav" role="button" tabindex="0" data-nome="${esc(l.nome.toLowerCase())}" data-act="open-job" data-job="${esc(l.lavoro)}"><div class="lav-head"><div class="t">${esc(l.nome)}</div><button class="btn s trash-job" data-act="confirm-trash" data-job="${esc(l.lavoro)}" aria-label="Sposta cantiere nel cestino">Elimina</button></div><div class="m">${esc(l.creato)} · ${l.pagine_totali} pagine${l.consumo&&l.consumo.chiamate?" · "+tokens(l.consumo):""}</div><div><span class="pill ${c}">${esc(e)}</span></div>${barraConti(l)}<div class="apri">Apri →</div></div>`}).join(""):`<div class="note" style="align-self:center">Nessun cantiere ancora. Carica i tuoi documenti oppure crea un cantiere di prova.</div>`;filtra($("cerca").value)}).catch(()=>{})}
function filtra(q){q=(q||"").trim().toLowerCase();document.querySelectorAll("#lavori .lav").forEach(e=>e.classList.toggle("hidden",!!q&&!e.dataset.nome.includes(q)))}

/* ---------- lavoro ---------- */
function apriLavoro(){ultimoEv=0;giaVisti=new Set();risultatoCaricato=false;inizio=true;pagMostrata=null;
 $("feed").innerHTML="";$("feed-live").classList.add("hidden");$("crops").innerHTML="";ris=null;passoScelto=null;passoAttuale=-1;firmaOrdine="";stato=null;$("ordine").innerHTML="";$("vecchio").classList.add("hidden");
 $("lookpage").innerHTML='<div class="scan"></div>';$("lookfile").textContent="In attesa delle pagine…";$("thought").textContent="Le pagine compaiono qui mentre vengono lette.";
 $("bins").innerHTML=Object.entries(FAM).map(([k,f])=>`<button type="button" class="card bin" id="bin-${k}" data-act="family" data-family="${k}"><div class="h"><div class="lab"><span class="sw" style="background:${f.c}"></span>${f.n}</div><div class="n" style="color:${f.c}">0</div></div><div class="stack"></div></button>`).join("");
 aggiorna()}  // poi è il ciclo di poll in app.js a tenerlo aggiornato
async function aggiorna(){if(!L)return;
 try{stato=await api(`/api/lavori/${L}/stato`)}catch(e){$("titolo").innerHTML=`Cantiere non trovato · <a href="#" data-act="home">torna ai tuoi cantieri</a>`;return}
 $("crumb").innerHTML=`/ <b>${esc(stato.nome)}</b>`;
 const p=stato.fase==="pronto"?100:stato.percentuale;
 $("barv").style.width=p+"%";$("ringv").style.strokeDashoffset=169.6*(1-p/100);$("ringt").textContent=p+"%";$("prog").setAttribute("aria-valuenow",p);
 $("titolo").textContent={preparazione:"Preparo le pagine",lettura:"Smisto e leggo le pagine",composizione:"Collego i documenti e preparo l'Excel",pronto:"Lavoro completato",errore:stato.motivo||"Nessuna pagina leggibile"}[stato.fase];
 const fatte=stato.lette+stato.non_lette.length;
 $("bart").textContent=`${fatte} di ${stato.pagine_totali} pagine · ${stato.file} file`;
 $("bare").textContent=stato.non_lette.length?`${stato.non_lette.length} pagine non lette`:"";
 $("bartok").textContent=tokens(stato.consumo);
 const ord=["preparazione","lettura","composizione","pronto"],i=ord.indexOf(stato.fase);
 passi();ricevuti();ordine();fasi();
 const vecchio=!!(stato.riepilogo&&stato.fase!=="pronto"&&ris);
 $("vecchio").classList.toggle("hidden",!vecchio);
 if(vecchio)$("vecchio").textContent="Ci sono pagine nuove o non ancora lette: il risultato e l'Excel che vedi sono della versione precedente. Si aggiornano da soli alla fine dell'analisi.";
 $("lookdot").style.visibility=stato.fase==="pronto"?"hidden":"visible";
 $("lookpage").classList.toggle("fermo",stato.fase==="pronto");
 // pagine nei contenitori
 const nuove=stato.pagine.filter(x=>x.famiglia&&!giaVisti.has(x.pid));
 nuove.forEach((x,k)=>{giaVisti.add(x.pid);if(inizio)metti(x);else setTimeout(()=>vola(x),k*180)});
 Object.keys(FAM).forEach(k=>{$("bin-"+k).querySelector(".n").textContent=stato.per_famiglia[k]||0});
 // eventi
 const ev=await api(`/api/lavori/${L}/eventi?da=${ultimoEv}`).catch(()=>[]);
 ultimoEv+=ev.length;ev.forEach(evento);
 const vista=[...ev].reverse().find(e=>e.pid&&e.tipo in FASE_PAGINA);if(vista)inEsame(vista);
 const ultimo=ev.length?ev[ev.length-1].t:null;if(ultimo)window._ultimoT=ultimo;
 $("idle").classList.toggle("hidden",!(stato.fase==="lettura"&&typeof agentState!=="undefined"&&agentState.busy&&agentState.job===L&&window._ultimoT&&Date.now()/1000-window._ultimoT>180));
 inizio=false;
 if(stato.fase==="pronto"&&!risultatoCaricato){risultatoCaricato=true;risultato()}}
function img(pid){return `/api/lavori/${L}/miniature/${pid}.png`}
function metti(x){const st=$("bin-"+x.famiglia).querySelector(".stack");if(st.children.length<18)st.insertAdjacentHTML("beforeend",`<img src="${img(x.pid)}" alt="">`)}
function vola(x){if(!$("lookpage").offsetParent||stato.fase==="pronto"||document.hidden){metti(x);return}const bin=$("bin-"+x.famiglia),src=$("lookpage").getBoundingClientRect(),dst=bin.getBoundingClientRect();
 const el=document.createElement("img");el.className="flyer";el.src=img(x.pid);document.body.appendChild(el);
 const a=el.animate([{left:src.left+src.width/2+"px",top:src.top+src.height/3+"px",transform:"scale(3)",opacity:.95},{left:dst.left+dst.width/2+"px",top:dst.top+40+"px",transform:"scale(1)",opacity:1}],{duration:700,easing:"cubic-bezier(.3,.7,.2,1)",fill:"forwards"});
 a.onfinish=()=>{el.remove();metti(x);bin.classList.remove("flash");void bin.offsetWidth;bin.classList.add("flash")}}
const TIPI={ricevuti:["Ricevuti","n"],preparate:["Preparazione","g"],fermata:["Fermata","o"],ripresa:["Ripresa","b"],
 errore:["Errore","r"],avviso:["Avviso","o"],mappa:["Riconoscimento","g"],componi:["Collegamento","b"],pronto:["Pronto","g"]};
// eventi di avanzamento: aggiornano sempre la stessa riga invece di aggiungerne una per file o per pagina
const VIVI={file:"Preparazione",pagina:"Preparazione",mappa_pagina:"Riconoscimento",lettura:"Lettura",testo_pagina:"Lettura del testo",lettura_pagina:"Lettura",scheda:"Lettura",correzione:"Lettura",ritaglio:"Lettura",nota:"Lettura"};
function rigaViva(e){let testo=e.testo||"";
 if(e.tipo==="file")testo=`File ${e.n} di ${e.totale}: ${testo}`;
 if(e.tipo==="scheda"&&FAM[e.famiglia])testo=`${FAM[e.famiglia].n} · ${testo}`;
 $("feed-live").innerHTML=`<time>${esc(e.ora)}</time><span class="pill b">${VIVI[e.tipo]}</span><span>${esc(testo)}</span>`;
 $("feed-live").classList.remove("hidden")}
function evento(e){
 if(e.tipo==="nota"){$("thought").innerHTML=`<b>Agente.</b> ${esc(e.testo)}`}
 if(e.tipo==="ritaglio"&&e.ritaglio){$("crops").insertAdjacentHTML("afterbegin",`<img src="/api/ritagli/${encodeURIComponent(e.ritaglio)}" title="${esc(e.testo)}" role="button" tabindex="0" data-act="open-proof" data-url="/api/ritagli/${encodeURIComponent(e.ritaglio)}" data-title="Ritaglio: ${esc(e.testo)}">`);while($("crops").children.length>4)$("crops").lastChild.remove()}
 if(VIVI[e.tipo]){rigaViva(e);return}
 const t=TIPI[e.tipo];if(!t)return;
 const testo=e.testo||"";
 if(["preparate","mappa","componi","pronto","errore","fermata"].includes(e.tipo))$("feed-live").classList.add("hidden");
 $("feed").insertAdjacentHTML("afterbegin",`<div class="ev"><time>${esc(e.ora)}</time><span class="pill ${t[1]}">${t[0]}</span><span>${esc(testo)}</span></div>`);
 while($("feed").children.length>8)$("feed").lastChild.remove()}
let pagMostrata=null;
// che cosa sta facendo l'app sulla pagina: testo sotto l'immagine
const FASE_PAGINA={pagina:["Preparazione","Divido il file in pagine e controllo il verso…"],
 mappa_pagina:["Riconoscimento","DeepSeek guarda la pagina: che documento è, se c'è un timbro…"],
 testo_pagina:["Lettura del testo","Riconosco parole e tabelle della scansione…"],
 lettura_pagina:["Lettura","Capisco che documento è e cerco i dati: DDT, certificato, colata…"],scheda:null};
function nomePagina(pid,testo){const p=stato&&stato.pagine.find(x=>x.pid===pid);return p?`${p.file} · pagina ${p.pagina}`:String(testo||pid).replace(/^(Lettura|Testo|Riconosco): /,"")}
function inEsame(e){$("lookfile").textContent=(e.tipo==="scheda"?"Letta: ":"")+nomePagina(e.pid,e.testo);
 if(e.tipo==="scheda"){const f=FAM[e.famiglia];$("thought").innerHTML=`<b>${esc(f?f.n:e.famiglia)}.</b> ${esc(e.testo)}`;mostraPagina(e.pid,true);return}
 const [t,d]=FASE_PAGINA[e.tipo];$("thought").innerHTML=`<b>${t}.</b> ${d}`;mostraPagina(e.pid,false)}
const SCANSIONE_MS=2400; // un passaggio della linea di scansione (come l'animazione CSS "scan")
async function mostraPagina(pid,conZone){const box=$("lookpage");
 if(pagMostrata!==pid){pagMostrata=pid;box.innerHTML=`<img src="/api/lavori/${L}/pagine/${pid}.png" alt="pagina"><div class="scan"></div>`;
  // parole riconosciute: compaiono quando la linea di scansione ci passa sopra
  api(`/api/lavori/${L}/pagine/${pid}/parole`).then(d=>{if(pagMostrata!==pid)return;
   const html=d.riquadri.map(([x0,y0,x1,y1])=>`<div class="w${d.origine==="ocr"?" blocco":""}" style="left:${x0/10}%;top:${y0/10}%;width:${Math.max(x1-x0,4)/10}%;height:${Math.max(y1-y0,4)/10}%;animation-delay:${Math.round(y0/1000*SCANSIONE_MS)}ms"></div>`).join("");
   box.insertAdjacentHTML("beforeend",html);
   if(!d.riquadri.length)box.insertAdjacentHTML("beforeend",'<div class="righe"></div>')}).catch(()=>{})}
 if(!conZone)return;
 try{const d=await api(`/api/lavori/${L}/pagine/${pid}`);if(pagMostrata!==pid||!d.scheda)return;
  const zone=[];const s=d.scheda;Object.values(s.testata||{}).forEach(v=>v.v&&v.zona&&v.zona.length&&zone.push(v.zona));
  (s.timbri||[]).forEach(t=>t.zona&&t.zona.length&&zone.push(t.zona));(s.righe||[]).slice(0,6).forEach(r=>r.colata&&r.colata.zona&&r.colata.zona.length&&zone.push(r.colata.zona));
  box.querySelectorAll(".box").forEach(b=>b.remove());
  zone.slice(0,12).forEach(([x0,y0,x1,y1],k)=>setTimeout(()=>box.insertAdjacentHTML("beforeend",`<div class="box" style="left:${x0/10}%;top:${y0/10}%;width:${(x1-x0)/10}%;height:${(y1-y0)/10}%"></div>`),k*120))}catch(e){}}


/* ---------- fasi del lavoro: una riga per fase, con barra e conteggio ---------- */
function fasi(){if(!stato)return;
 const g=(typeof agentState!=="undefined"&&agentState.busy&&agentState.job===L)?agentState:null,a=g&&g.avanzamento;
 const tot=stato.pagine_totali,fatte=stato.lette+stato.non_lette.length,pronto=stato.fase==="pronto",fermo=stato.fermato&&!g;
 const riga=(n,st,quanto,testo)=>`<div class="fase ${st}"><span class="fi">${st==="fatto"?"✓":st==="ferma"?"⏸":n}</span><span class="fn">${["","Ricevuti","Preparazione","Lettura e smistamento","Collegamento dei documenti","Excel e prove"][n]}</span><span class="fb"><i style="width:${quanto}%"></i></span><span class="fm">${esc(testo)}</span></div>`;
 const pr=stato.preparazione,perc=(x,y)=>y?Math.round(100*x/y):0;
 const r=[riga(1,stato.file?"fatto":"ora",stato.file?100:30,stato.file?`${stato.file} file`:"Arrivano i file…")];
 r.push(stato.preparing?riga(2,"ora",pr&&pr.totale?perc(pr.n,pr.totale):8,pr&&pr.totale?`File ${pr.n} di ${pr.totale}`:"Preparo le pagine…")
  :riga(2,tot?"fatto":"",tot?100:0,tot?`${tot} pagine pronte`:"In attesa"));
 let lst,lq,lt;
 if(a&&a.passo==="mappa"){lst="ora";lq=perc(a.n,a.totale);lt=`Riconosco i tipi ${a.n} di ${a.totale}`}
 else if(a&&a.passo==="testo"){lst="ora";lq=perc(a.n,a.totale);lt=`Testo scansioni ${a.n} di ${a.totale}`}
 else if(a&&a.passo==="lettura"){lst="ora";lq=perc(fatte,tot);lt=`${fatte} di ${tot} pagine`}
 else if(tot&&fatte>=tot){lst="fatto";lq=100;lt=`${fatte} di ${tot} pagine`}
 else{lst=fermo&&tot?"ferma":g&&tot?"ora":"";lq=perc(fatte,tot);lt=tot?`${fatte} di ${tot} pagine`+(fermo?" · ferma":""):"In attesa"}
 r.push(riga(3,lst,lq,lt));
 const ex=a&&a.passo==="excel";
 r.push(riga(4,pronto?"fatto":ex?"ora":"",pronto?100:ex?60:0,pronto?"Fatto":ex?"In corso…":"In attesa"));
 r.push(riga(5,pronto?"fatto":ex?"ora":"",pronto?100:ex?40:0,pronto?"Pronti da scaricare":ex?"In corso…":"In attesa"));
 $("fasi").innerHTML=r.join("");
 if(pronto&&!g)$("feed-live").classList.add("hidden")}

/* ---------- passi ---------- */
const PASSI=[
 {k:"carica",n:"Ricevo i file",t:"I file sono arrivati: li divido in pagine singole. Gli originali restano invariati."},
 {k:"smisto",n:"Smisto e leggo",t:"Guardo ogni pagina, la leggo e la metto nella sua famiglia. Clicca un contenitore per vedere le sue pagine."},
 {k:"ordine",n:"Metto in ordine",t:"Le pagine in fila nell'ordine della catena, come nello ZIP finale. Quelle evidenziate erano girate e le raddrizzo."},
 {k:"risultato",n:"Risultato",t:"Lo stato del cantiere, l'Excel, lo ZIP ordinato e cosa chiedere a ogni fornitore."}];
function passoDaFase(){return {preparazione:0,lettura:1,composizione:2,pronto:3}[stato.fase]??0}
function passoAperto(i){return i===0||(i<=2&&stato.fase!=="preparazione")||(i===3&&!!ris)}
function passi(){const cur=passoDaFase();
 if(cur!==passoAttuale){passoAttuale=cur;passoScelto=null}
 let vis=passoScelto??cur;if(!passoAperto(vis))vis=Math.min(cur,1);
 const pronto=stato.fase==="pronto";
 $("passi").innerHTML=PASSI.map((s,i)=>`<button class="${i<cur||pronto?"fatto":i===cur?"ora":""} ${i===vis?"visto":""}" ${passoAperto(i)?"":"disabled"} data-act="step" data-i="${i}"><span class="n">${i<cur||pronto?"✓":i+1}</span><span class="t">${s.n}</span></button>`).join("");
 PASSI.forEach((s,i)=>$("p-"+s.k).classList.toggle("on",i===vis));
 $("ptitolo").textContent=`${vis+1}. ${PASSI[vis].n}`;$("ptesto").textContent=PASSI[vis].t}
function scegliPasso(i){passoScelto=i;passi();if(PASSI[i].k==="ordine"){firmaOrdine="";ordine()}}
function ricevuti(){$("ricevuti").innerHTML=stato.fase==="errore"?`<b>${esc(stato.motivo||"Nessuna pagina leggibile")}</b>`:stato.fase==="preparazione"?`<div class="who"><span class="dot"></span>Preparo le pagine…</div>`:
 `<b>${stato.file} file ricevuti, ${stato.pagine_totali} pagine pronte.</b><div class="note" style="margin-top:6px">Gli originali restano invariati. Se arrivano altri documenti usa «Aggiungi file»: le pagine già lette non vengono rilette.</div>`}

/* ---------- ordine della catena (come lo ZIP ordinato) ---------- */
const CARTELLE=[["Costruttore",["packing_costruttore","dop_costruttore"]],["DDT",["ddt"]],["Certificati 3.1",["certificato_31","lettera_accompagnamento"]],["DoP e CE",["dop_ce_prodotto"]]];
function vediPagina(pid){$("mframe").classList.add("hidden");$("mbody").classList.remove("hidden");$("mopen").classList.add("hidden");$("mbody").innerHTML="";mostraModale();safe(()=>pagina(pid))}
function ordine(){if(!stato||!$("p-ordine").classList.contains("on"))return;
 const lette=stato.pagine.filter(x=>x.famiglia);const firma=lette.length+":"+stato.fase;if(firma===firmaOrdine)return;firmaOrdine=firma;
 const fogli=ps=>`<div class="fogli">${ps.map((x,k)=>`<img src="${img(x.pid)}" alt="" style="animation-delay:${Math.min(k,40)*25}ms" class="${x.orientamento?"girata":""}" title="${esc(x.file)} · pagina ${x.pagina}${x.orientamento?" · girata di "+x.orientamento+"°, raddrizzata":""}" role="button" tabindex="0" data-act="view-page" data-pid="${esc(x.pid)}">`).join("")}</div>`;
 const gruppi=CARTELLE.map(([nome,fam],i)=>{const ps=lette.filter(x=>fam.includes(x.famiglia));
  const tinta=FAM[fam[0]].c,num=String(i+1).padStart(2,"0");
  return (i?'<div class="freccia">→</div>':"")+(ps.length?`<div class="card gruppo" style="--c:${tinta}"><div class="gt"><span>${num} · ${nome}</span><span style="color:${tinta}">${ps.length}</span></div>${fogli(ps)}</div>`
   :`<div class="card gruppo manca" style="--c:var(--red)"><div class="gt"><span>${num} · ${nome}</span></div>${stato.fase==="lettura"?"Ancora nessuna pagina":"Manca: nessuna pagina di questo tipo"}</div>`)}).join("");
 const via=lette.filter(x=>["da_escludere","illeggibile"].includes(x.famiglia));
 const girate=lette.filter(x=>x.orientamento).length;
 $("ordine").innerHTML=`<div class="gruppi">${gruppi}</div>
  ${via.length?`<div class="card gruppo via" style="--c:var(--soft);margin-top:12px"><div class="gt"><span>99 · Non usati (fuori dalla catena)</span><span>${via.length}</span></div>${fogli(via)}</div>`:""}
  <div class="acts" style="margin-top:14px;align-items:center">${girate?`<span class="pill o">↻ ${girate} pagine girate: nello ZIP sono raddrizzate</span>`:""}
  ${stato.fase==="pronto"?`<button class="btn s" data-act="download" data-tipo="fascicolo-ordinato"><svg class="ic"><use href="#fold"/></svg>Scarica lo ZIP in questo ordine</button>`:`<span class="note" style="margin:0">Lo ZIP ordinato sarà pronto alla fine.</span>`}</div>`}

/* ---------- download con errori leggibili ---------- */
async function scaricaFile(tipo){const r=await fetch(`/api/lavori/${L}/${tipo}`);
 if(!r.ok){let d="";try{d=(await r.json()).detail}catch(e){}throw new Error(d?d.charAt(0).toUpperCase()+d.slice(1)+".":"Download non riuscito.")}
 const nome=(r.headers.get("Content-Disposition")||"").match(/filename="([^"]+)"/)?.[1]||tipo+".zip";
 const u=URL.createObjectURL(await r.blob());const a=document.createElement("a");a.href=u;a.download=nome;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),2000)}

/* ---------- famiglie ---------- */
function famiglia(k){if(!stato)return;const ps=stato.pagine.filter(x=>x.famiglia===k);
 $("mtitle").textContent=`${FAM[k].n} · ${ps.length} pagine`;$("mopen").classList.add("hidden");
 $("mbody").innerHTML=ps.length?`<div class="grid-pg">${ps.map(x=>`<button type="button" class="pg" data-act="page" data-pid="${esc(x.pid)}"><img src="${img(x.pid)}" alt=""><div>${esc(x.file)} · p${x.pagina}</div></button>`).join("")}</div>`:`<div class="note">Nessuna pagina in questa famiglia.</div>`;
 $("mframe").classList.add("hidden");$("mbody").classList.remove("hidden");mostraModale()}
async function pagina(pid){const d=await api(`/api/lavori/${L}/pagine/${pid}`);const s=d.scheda||{};
 $("mtitle").textContent=`${d.pagina.file} · pagina ${d.pagina.pagina}`;
 $("mbody").innerHTML=`<p class="sub" style="margin:0 0 12px">${esc(s.motivo||"")}</p>${(s.avvisi||[]).map(a=>`<div class="pill o" style="margin:0 6px 8px 0">${esc(a)}</div>`).join("")}<img src="/api/lavori/${L}/pagine/${pid}.png" style="width:100%;border-radius:8px;border:1px solid var(--line)">`}
function apri(url,titolo){$("mtitle").textContent=titolo;$("mopen").href=url;$("mopen").classList.remove("hidden");
 $("mframe").src=url;$("mframe").classList.remove("hidden");$("mbody").classList.add("hidden");mostraModale()}
function mostraModale(){const m=$("modal");if(!m.open)m.showModal()}
function chiudi(){const m=$("modal");if(m.open)m.close();$("mframe").src="about:blank"}
$("modal").addEventListener("close",()=>{$("mframe").src="about:blank"});
$("modal").onclick=e=>{if(e.target.id==="modal")chiudi()};

/* ---------- tabella dei dati (versione A): cella -> pagina evidenziata, documento e perché ---------- */
let tab=null,celSel=null;
const corto=f=>String(f||"").split("/").pop();
async function mostraTabella(){const sez=$("tabella-dati");
 if(!sez.classList.contains("hidden")){sez.classList.add("hidden");$("vedi-tabella").textContent="▦ Vedi tabella";return}
 tab=await api(`/api/lavori/${L}/tabella`);sez.classList.remove("hidden");$("vedi-tabella").textContent="▦ Nascondi tabella";
 const docLink=d=>`<a class="doc" href="#" title="Apri il documento originale" data-act="open-original" data-pid="${esc(d.pid)}" data-pagina="${Number(d.pagina)||1}" data-nome="${esc(corto(d.file))}">📄 ${esc(corto(d.file))} · p. ${d.pagina}</a>`;
 $("tdati").innerHTML=`<tr><th>N</th><th>Voce</th><th>Stato</th>${tab.colonne.map(c=>`<th>${esc(c)}</th>`).join("")}</tr>`+
  tab.voci.map((v,i)=>`<tr><td>${v.n}</td><td>${esc(v.voce)}</td><td><span class="pill ${STATI[v.stato]}">${v.stato}</span></td>${tab.colonne.map(c=>{const x=v.celle[c]||{v:"",documenti:[]};
   return `<td class="cella" tabindex="0" data-i="${i}" data-c="${esc(c)}">${x.v?esc(x.v):'<span class="vuoto">—</span>'}${x.documenti.slice(0,2).map(docLink).join("")}</td>`}).join("")}</tr>`).join("");
 $("tdati").onclick=e=>{if(e.target.closest("[data-act]"))return;const td=e.target.closest("td.cella");if(td)scegliCella(td)};
 $("tdati").onkeydown=e=>{if((e.key==="Enter"||e.key===" ")&&e.target.matches("td.cella")){e.preventDefault();scegliCella(e.target)}};
 const prima=$("tdati").querySelector('td.cella[data-c="COLATA"]')||$("tdati").querySelector("td.cella");
 if(prima)scegliCella(prima);else $("dettaglio").innerHTML='<div class="note">Nessuna voce nel risultato.</div>';
 sez.scrollIntoView({behavior:"smooth",block:"start"})}
function scegliCella(td){$("tdati").querySelectorAll(".sel").forEach(x=>x.classList.remove("sel"));td.classList.add("sel");
 const v=tab.voci[td.dataset.i],c=td.dataset.c;celSel={v,c,k:0};dettaglio()}
function dettaglio(){const {v,c,k}=celSel,x=v.celle[c]||{v:"",perche:"",documenti:[]},d=x.documenti[k];
 const pagina=d?`<div class="pagina"><img src="/api/lavori/${L}/pagine/${d.pid}.png" alt="pagina">${d.zona&&d.zona.length===4?`<div class="box" style="left:${d.zona[0]/10}%;top:${d.zona[1]/10}%;width:${(d.zona[2]-d.zona[0])/10}%;height:${(d.zona[3]-d.zona[1])/10}%"></div>`:""}</div>`
  :'<div class="pagina"><div class="vuota">Per questo dato non c\'è una pagina nel fascicolo.</div></div>';
 const schede=x.documenti.length>1?`<div class="schede">${x.documenti.map((y,j)=>`<button class="btn s" style="height:28px;padding:0 10px${j===k?";border-color:var(--accent)":""}" data-act="doc-tab" data-k="${j}">${esc(corto(y.file))} · p. ${y.pagina}</button>`).join("")}</div>`:"";
 $("dettaglio").innerHTML=`${pagina}<div><h3>Voce ${v.n} · ${esc(v.voce)} → ${esc(c)}</h3><span class="pill ${STATI[v.stato]}">${v.stato}</span>
  <div class="k">Valore</div><div>${x.v?esc(x.v):"—"}</div>
  <div class="k">Documento</div><div>${d?`<a href="#" data-act="open-original" data-pid="${esc(d.pid)}" data-pagina="${Number(d.pagina)||1}" data-nome="${esc(corto(d.file))}">📄 ${esc(d.file)} · pagina ${d.pagina} — apri il documento</a>`:"—"}</div>${schede}
  <div class="k">Perché è stato usato</div><div>${esc(x.perche||"Risultato preparato con una versione precedente: rifai l'analisi per vedere il motivo.")}</div>
  ${d&&d.cit?`<div class="k">Testo letto sulla pagina</div><div class="cit">${esc(d.cit)}</div>`:""}
  ${v.note&&v.note.length?`<div class="k">Note della voce</div><div>${esc(v.note.join(" "))}</div>`:""}</div>`}
function apriOriginale(pid,pagina,nome){apri(`/api/lavori/${L}/originale/${pid}#page=${pagina}`,`${nome} · pagina ${pagina}`)}

/* ---------- risultato ---------- */
function esito(r){const c=r.conteggio,tot=r.voci.length;let pill,cls,titolo;
 if(!tot)[pill,cls,titolo]=["Da controllare","o","Nessuna voce trovata"];
 else if(c.MANCANTE)[pill,cls,titolo]=["Mancano documenti","r",`Mancano documenti per ${c.MANCANTE} ${c.MANCANTE===1?"voce":"voci"} su ${tot}`];
 else if(c["DA CONFERMARE"])[pill,cls,titolo]=["Da confermare","o",`${c["DA CONFERMARE"]} ${c["DA CONFERMARE"]===1?"voce":"voci"} su ${tot} da confermare`];
 else [pill,cls,titolo]=["Completato","g",`Tutto collegato: ${tot} voci`];
 $("esito-pill").className="pill "+cls;$("esito-pill").textContent=pill;$("esito-titolo").textContent=titolo;
 $("ressub").textContent=tot?`L'Excel e lo ZIP ordinato sono pronti con quello che c'è${c.MANCANTE||c["DA CONFERMARE"]?": quando arrivano i documenti mancanti usa «Aggiungi file» e rifaccio i collegamenti":""}. ${stato?stato.pagine_totali+" pagine da "+stato.file+" file. ":""}Ogni dato ha il collegamento alla pagina da cui viene.`
  :"Non ho trovato né la tabella del costruttore né DDT con materiali: controlla di aver caricato i documenti giusti.";
 const avvisi=[];
 if(r.avviso_packing)avvisi.push("Manca la tabella (packing) del costruttore: le voci sono prese dai DDT ricevuti dal costruttore, quindi al massimo DEDOTTO.");
 if(stato&&stato.non_lette.length)avvisi.push(`${stato.non_lette.length} pagine non lette dopo più tentativi: la lettura è incompleta.`);
 $("esito-avvisi").innerHTML=avvisi.map(a=>`<div class="avviso" style="margin:12px 0 0">${esc(a)}</div>`).join("")}
function fornitori(r){const per={};
 r.voci.forEach(v=>(v.richieste||[]).forEach(q=>{const f=v.fornitore||"Fornitore non individuato";((per[f]??={})[q]??=[]).push(v)}));
 const nomi=Object.keys(per);
 window._richieste=nomi.map(f=>`Buongiorno,\nper il cantiere ${stato?stato.nome:""} ci servono:\n`+Object.entries(per[f]).map(([q,vv])=>`- ${q} per: ${vv.map(v=>v.voce+(v.ddt?" (DDT "+v.ddt+")":"")).join(", ")}`).join("\n")+"\nGrazie.");
 $("fornitori").innerHTML=nomi.length?nomi.map((f,i)=>`<div class="card fornitore"><h3>${esc(f)}</h3><ul>${Object.entries(per[f]).map(([q,vv])=>`<li><b>${esc(q)}</b> per ${vv.length} ${vv.length===1?"voce":"voci"}</li>`).join("")}</ul><button class="btn s" data-act="copy-request" data-i="${i}">Copia richiesta</button></div>`).join("")
  :`<div class="note">Nessun documento da chiedere.</div>`}
function copiaRichiesta(i){navigator.clipboard.writeText(window._richieste[i]).then(()=>notify("Richiesta copiata: incollala in una mail al fornitore."),()=>notify("Copia non riuscita: seleziona il testo dall'Excel, foglio «Richieste ai fornitori»."))}
async function risultato(){let r;try{r=await api(`/api/lavori/${L}/risultato`)}catch(e){return}
 ris=r;esito(r);fornitori(r);if(stato)passi();$("tabella-dati").classList.add("hidden");$("vedi-tabella").textContent="▦ Vedi tabella";
 $("stati").innerHTML=Object.entries(STATI).map(([k,c])=>`<div class="stato ${c}"><div class="v">${r.conteggio[k]||0}</div><div class="l">${k}</div></div>`).join("")}
