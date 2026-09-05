export type ChatMessage={role:'user'|'assistant';content:string;time:string}
export type Candidate={crew_id:string;name?:string;rank?:string;base?:string;legal:boolean;cost_inr?:number;delay_hours?:number;coverage?:string;reason?:string;checks?:Record<string,any>;reserve?:boolean;reachability_minutes?:number;aircraft_ratings?:string[];deadhead?:boolean}
