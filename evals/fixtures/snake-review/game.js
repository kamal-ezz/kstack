import {SIZE,DIRECTIONS,createGame,canTurn,step} from './engine.js';
const $=id=>document.getElementById(id);
const canvas=$('board'), ctx=canvas.getContext('2d');
let state=createGame(), mode='ready', pace='classic', queue=[], timer;
let best=0;
try { const saved=Number(localStorage.getItem('pocket-snake-best')); if(Number.isFinite(saved)&&saved>0) best=saved; } catch { /* Storage can be unavailable in private environments. */ }
const speeds={chill:180,classic:125,fast:80};
function draw(){
  ctx.fillStyle='#dce3c9';ctx.fillRect(0,0,600,600);
  ctx.strokeStyle='#b5c39e35';ctx.lineWidth=1;
  for(let i=0;i<=SIZE;i++){ctx.beginPath();ctx.moveTo(i*30,0);ctx.lineTo(i*30,600);ctx.stroke();ctx.beginPath();ctx.moveTo(0,i*30);ctx.lineTo(600,i*30);ctx.stroke();}
  if(state.food){const {x,y}=state.food;ctx.fillStyle='#cf603b';ctx.beginPath();ctx.arc(x*30+15,y*30+16,9,0,Math.PI*2);ctx.fill();ctx.fillStyle='#506b39';ctx.fillRect(x*30+15,y*30+3,3,6);}
  state.snake.forEach((part,i)=>{ctx.fillStyle=i===0?'#2f4b32':'#547148';ctx.beginPath();ctx.roundRect(part.x*30+2,part.y*30+2,26,26,5);ctx.fill();});
  const head=state.snake[0], d=DIRECTIONS[state.direction];
  ctx.fillStyle='#e8edda';
  for(const side of [-1,1]){const x=head.x*30+15+d.x*6+(d.y?side*6:0),y=head.y*30+15+d.y*6+(d.x?side*6:0);ctx.fillRect(x-2,y-2,4,4);}
  $('score').textContent=String(state.score).padStart(3,'0');$('best').textContent=String(best).padStart(3,'0');
}
function showOverlay(title,hint,button){$('message').innerHTML=title;$('hint').textContent=hint;$('start').textContent=button;$('overlay').hidden=false;$('shortcut').textContent=mode==='paused'?'or press Space to resume':'or press Space to start';}
function updateControls(){ $('pause').disabled=mode==='ready'||mode==='ended';$('pause').innerHTML=mode==='paused'?'▶ <span>Resume</span>':'Ⅱ <span>Pause</span>';$('pause').setAttribute('aria-label',mode==='paused'?'Resume game':'Pause game');$('status').textContent={ready:'READY TO PLAY',playing:'IN THE GROOVE',paused:'TAKE A BREATHER',ended:'ANOTHER ROUND?'}[mode]; }
function tick(){state=step(state,queue.shift()||state.direction);if(state.score>best){best=state.score;try{localStorage.setItem('pocket-snake-best',String(best));}catch{}}
  draw();if(state.ended){clearInterval(timer);mode='ended';showOverlay(state.won?'You ate it all.':'That’s a wrap.',`You scored ${state.score}. ${state.won?'A perfect game!':'There’s always another bite.'}`,'Play again ↗');$('announcement').textContent=`Game over. Score ${state.score}.`;updateControls();}}
function start(){clearInterval(timer);state=createGame();queue=[];mode='playing';$('overlay').hidden=true;timer=setInterval(tick,speeds[pace]);draw();updateControls();}
function pause(){if(mode==='playing'){clearInterval(timer);mode='paused';showOverlay('Take your time.','Your next bite can wait.','Keep going ↗');}else if(mode==='paused'){mode='playing';$('overlay').hidden=true;timer=setInterval(tick,speeds[pace]);}updateControls();}
function turn(direction){if(mode!=='playing'||queue.length>=2)return;const previous=queue.at(-1)||state.direction;if(direction!==previous&&canTurn(previous,direction))queue.push(direction);}
$('start').addEventListener('click',()=>mode==='paused'?pause():start());$('pause').addEventListener('click',pause);
const keys={ArrowUp:'up',w:'up',ArrowDown:'down',s:'down',ArrowLeft:'left',a:'left',ArrowRight:'right',d:'right'};
document.addEventListener('keydown',e=>{if(e.target.closest('button,a,input,select')&&(e.key===' '||e.key==='Enter'))return;const key=e.key.length===1?e.key.toLowerCase():e.key;if(keys[key]){e.preventDefault();turn(keys[key]);}else if(key===' '){e.preventDefault();if(e.repeat)return;mode==='ready'||mode==='ended'?start():pause();}else if(key==='r'&&!e.repeat)start();});
document.querySelectorAll('[data-direction]').forEach(button=>button.addEventListener('click',()=>turn(button.dataset.direction)));
document.querySelectorAll('[data-speed]').forEach(button=>button.addEventListener('click',()=>{pace=button.dataset.speed;document.querySelectorAll('[data-speed]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));if(mode==='playing'){clearInterval(timer);timer=setInterval(tick,speeds[pace]);}}));
document.addEventListener('visibilitychange',()=>{if(document.hidden&&mode==='playing')pause();});
let touch;
canvas.addEventListener('touchstart',e=>{touch=e.touches[0];},{passive:true});
canvas.addEventListener('touchmove',e=>{if(mode==='playing')e.preventDefault();},{passive:false});
canvas.addEventListener('touchend',e=>{if(!touch)return;const dx=e.changedTouches[0].clientX-touch.clientX,dy=e.changedTouches[0].clientY-touch.clientY;if(Math.max(Math.abs(dx),Math.abs(dy))>15)turn(Math.abs(dx)>Math.abs(dy)?(dx>0?'right':'left'):(dy>0?'down':'up'));touch=null;});
draw();updateControls();
