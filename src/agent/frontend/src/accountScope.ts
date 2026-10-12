export function ownsHistory(state:unknown,scope:string):boolean{
 return !!state&&typeof state==='object'&&(state as {account?:unknown}).account===scope;
}
