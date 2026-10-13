import type {ChartReference} from './api/types';
export async function readReference(file:File):Promise<ChartReference>{
 const types=['image/png','image/jpeg','image/webp','application/pdf'];
 if(!types.includes(file.type))throw new Error('PNG, JPG, WebP 또는 PDF를 선택해 주세요.');
 if(file.size>4_000_000)throw new Error('참고 파일은 하나당 최대 4MB입니다.');
 const data_url=await new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=()=>reject(new Error('파일을 읽지 못했습니다.'));reader.readAsDataURL(file);});
 return {name:file.name,mime:file.type,data_url};
}
