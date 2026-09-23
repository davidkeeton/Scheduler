export type TimeWindow={start:string;end:string};
const defaultZone='America/Vancouver';
const compact=(value:string)=>new Date(value).toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'');
const escapeText=(text:string)=>text.replace(/\\/g,'\\\\').replace(/,/g,'\\,').replace(/;/g,'\\;').replace(/\n/g,'\\n');

export function exportAvailability(windows:TimeWindow[],name:string){
 const stamp=compact(new Date().toISOString());
 const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Coverage Scheduler//Casual Availability//EN','CALSCALE:GREGORIAN','X-WR-CALNAME:'+escapeText(name+' availability')];
 for(const [index,window] of windows.entries()){
  if(new Date(window.start)>=new Date(window.end))continue;
  lines.push('BEGIN:VEVENT','UID:availability-'+index+'-'+compact(window.start)+'@coverage-scheduler','DTSTAMP:'+stamp,'DTSTART:'+compact(window.start),'DTEND:'+compact(window.end),'SUMMARY:'+escapeText('Available - '+name),'END:VEVENT');
 }
 lines.push('END:VCALENDAR');
 return lines.join('\r\n')+'\r\n';
}

function zoneParts(instant:number,zone:string){
 const values=new Intl.DateTimeFormat('en-CA',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(instant));
 return Object.fromEntries(values.map(p=>[p.type,p.value]));
}
function localToUtc(compactValue:string,zone:string){
 const match=/^(\d{4})(\d{2})(\d{2})(?:T(\d{2})(\d{2})(\d{2}))?$/.exec(compactValue);
 if(!match)throw Error('Unsupported calendar date format');
 const desired=Date.UTC(+match[1],+match[2]-1,+match[3],+(match[4]||0),+(match[5]||0),+(match[6]||0));
 let candidate=desired;
 for(let i=0;i<3;i++){
  const p=zoneParts(candidate,zone);
  const actual=Date.UTC(+p.year,+p.month-1,+p.day,+p.hour,+p.minute,+(match[6]||0));
  candidate+=desired-actual;
 }
 return new Date(candidate).toISOString();
}
function eventTime(line:string){
 const colon=line.indexOf(':');if(colon<0)throw Error('Calendar event is missing a date');
 const head=line.slice(0,colon),value=line.slice(colon+1).trim();
 if(/^\d{8}T\d{6}Z$/.test(value)){
  const m=/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/.exec(value)!;
  return new Date(Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6])).toISOString();
 }
 const zone=/TZID=([^;:]+)/i.exec(head)?.[1]||defaultZone;
 try{return localToUtc(value,zone)}catch{throw Error('Unsupported calendar time zone or date: '+zone)}
}
export function importAvailability(text:string):TimeWindow[]{
 const lines=text.replace(/\r\n/g,'\n').replace(/\n[ \t]/g,'').split('\n').map(x=>x.trim());
 if(!lines.includes('BEGIN:VCALENDAR'))throw Error('Select an .ics calendar file');
 const windows:TimeWindow[]=[];let event:string[]|null=null;
 for(const line of lines){
  if(line==='BEGIN:VEVENT'){event=[];continue}
  if(line==='END:VEVENT'){
   if(!event)continue;
   if(event.some(x=>x.startsWith('RRULE')||x.startsWith('RDATE')||x.startsWith('EXDATE')))throw Error('Recurring calendar events are not supported; export individual dates first');
   const start=event.find(x=>x.startsWith('DTSTART'));
   const end=event.find(x=>x.startsWith('DTEND'));
   if(!start||!end)throw Error('An event is missing its start or end');
   const window={start:eventTime(start),end:eventTime(end)};
   if(new Date(window.start)>=new Date(window.end))throw Error('An availability event ends before it starts');
   windows.push(window);event=null;continue;
  }
  if(event)event.push(line);
 }
 if(!windows.length)throw Error('No dated availability events found');
 return [...new Map(windows.map(x=>[x.start+'|'+x.end,x])).values()].sort((a,b)=>a.start.localeCompare(b.start));
}
