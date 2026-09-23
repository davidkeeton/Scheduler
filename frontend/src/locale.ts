// Translation boundary for interface copy and date formatting.
export const locale = 'en-CA';
export const labels = {onCallHeading:'On-call now and upcoming',current:'ON CALL NOW',upcoming:'UPCOMING',staffed:'Staffed',standby:'Standby',missingPhone:'Phone number missing'};
export function formatDateTime(value:string,timeZone:string){return new Intl.DateTimeFormat(locale,{timeZone,weekday:'short',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}).format(new Date(value));}
