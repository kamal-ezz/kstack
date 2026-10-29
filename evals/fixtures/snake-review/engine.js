export const SIZE = 20;
export const DIRECTIONS = { up: {x:0,y:-1}, down:{x:0,y:1}, left:{x:-1,y:0}, right:{x:1,y:0} };
export function placeFood(snake, random = Math.random) {
  const empty = [];
  for (let y=0;y<SIZE;y++) for(let x=0;x<SIZE;x++) {
    if (!snake.some(part=>part.x===x && part.y===y)) empty.push({x,y});
  }
  return empty.length ? empty[Math.floor(random()*empty.length)] : null;
}
export function createGame() {
  const snake = [{x:8,y:10},{x:7,y:10},{x:6,y:10},{x:5,y:10}];
  return {snake, direction:'right', food:{x:14,y:10}, score:0, ended:false, won:false};
}
export function canTurn(from, to) {
  const current = DIRECTIONS[from], next = DIRECTIONS[to];
  return Boolean(current && next) && (current.x + next.x !== 0 || current.y + next.y !== 0);
}
export function step(state, direction = state.direction, random = Math.random) {
  if(state.ended) return state;
  if(!canTurn(state.direction,direction)) direction=state.direction;
  const delta=DIRECTIONS[direction];
  const head={x:state.snake[0].x+delta.x,y:state.snake[0].y+delta.y};
  const eating=head.x===state.food?.x && head.y===state.food?.y;
  const body=eating ? state.snake : state.snake.slice(0,-1);
  if(head.x<0 || head.y<0 || head.x>=SIZE || head.y>=SIZE || body.some(p=>p.x===head.x && p.y===head.y)) return {...state,ended:true};
  const snake=[head,...state.snake];
  if(!eating) snake.pop();
  const food=eating ? placeFood(snake,random) : state.food;
  return {...state,snake,direction,food,score:state.score+(eating?10:0),ended:food===null,won:food===null};
}
