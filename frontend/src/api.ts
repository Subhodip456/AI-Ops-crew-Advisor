export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
async function request<T>(path:string, init?:RequestInit):Promise<T>{const res=await fetch(`${API_BASE}${path}`,{headers:{'Content-Type':'application/json',...(init?.headers||{})},...init});if(!res.ok){const text=await res.text();throw new Error(text||`HTTP ${res.status}`)}return res.json()}
export const api={
 health:()=>request<{status:string;sarvam_configured:boolean}>('/api/health'),
 chat:(message:string,history:any[])=>request<{answer:string}>('/api/chat',{method:'POST',body:JSON.stringify({message,history})}),
 disruption:(crew_id:string,date:string,pairing_id?:string)=>request<any>('/api/disruptions/analyze',{method:'POST',body:JSON.stringify({crew_id,date,pairing_id})}),
 replacements:(pairing_id:string,role:string)=>request<any>('/api/replacements/find',{method:'POST',body:JSON.stringify({pairing_id,role})}),
 ranking:(pairing_id:string,role:string)=>request<any>('/api/recommendations/rank',{method:'POST',body:JSON.stringify({pairing_id,role})}),
 crew:(id:string)=>request<any>(`/api/crew/${encodeURIComponent(id)}`),
 crewList:(role?:string)=>request<any[]>(`/api/crew${role?`?role=${encodeURIComponent(role)}`:''}`),
 flights:(date?:string)=>request<any[]>(`/api/flights${date?`?date=${encodeURIComponent(date)}`:''}`),
 reserves:()=>request<any[]>('/api/reserves'),
 rules:()=>request<any>('/api/rules')
}
