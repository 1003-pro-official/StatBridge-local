import type {SavedChat} from './graphChat';
export type AccountAnalysis={id:string;title:string;saved_at:number};
export function analysisEntries(local:SavedChat[],account:AccountAnalysis[]){
 const entries=new Map<string,{id:string;title:string;savedAt:number;local?:SavedChat;account?:AccountAnalysis}>();
 for(const item of account)entries.set(item.id,{id:item.id,title:item.title,savedAt:item.saved_at*1000,account:item});
 for(const item of local){const previous=entries.get(item.id);entries.set(item.id,{...previous,id:item.id,title:item.title,savedAt:Math.max(item.savedAt,previous?.savedAt||0),local:item});}
 return [...entries.values()].sort((a,b)=>b.savedAt-a.savedAt);
}
