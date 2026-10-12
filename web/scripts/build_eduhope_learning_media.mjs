// Original vector learning cues rendered to portable PNGs; no source-photo edits.
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {chromium} from '../frontend/node_modules/playwright/index.mjs';
const root=new URL('../seed-data/eduhope/illustrations/',import.meta.url);fs.mkdirSync(root,{recursive:true});
const drawings={
book:'<path d="M64 62Q112 44 160 70Q208 44 256 62V202Q208 184 160 210Q112 184 64 202Z"/><path d="M160 70V210M84 90Q116 80 142 98M180 98Q214 80 238 90M84 120Q116 110 142 128M180 128Q214 110 238 120"/>',
bus:'<rect x="48" y="62" width="224" height="128" rx="24"/><path d="M70 82H248V138H70ZM70 161H104M216 161H250"/><circle cx="92" cy="194" r="17"/><circle cx="228" cy="194" r="17"/>',
calendar:'<rect x="58" y="52" width="204" height="162" rx="16"/><path d="M58 94H262M103 36V68M218 36V68M86 125H109M148 125H172M210 125H233M86 163H109M148 163H172M210 163H233"/><circle cx="160" cy="163" r="23"/>',
meeting:'<circle cx="90" cy="80" r="24"/><circle cx="230" cy="80" r="24"/><path d="M54 176V138Q90 105 126 138V176M194 176V138Q230 105 266 138V176M64 183H258M160 115V65H203L222 85L203 105H160"/>',
interview:'<circle cx="86" cy="79" r="23"/><circle cx="228" cy="79" r="23"/><path d="M48 192V138Q86 112 122 138V192M192 192V138Q228 112 264 138V192M132 166H188M150 145V214"/><rect x="137" y="53" width="43" height="59" rx="5"/><path d="M148 70H170M148 85H170"/>',
balance:'<path d="M160 40V210M105 213H215M71 75H249M83 75L52 140H114ZM237 75L206 140H268Z"/><circle cx="160" cy="75" r="12"/>',
evidence:'<rect x="52" y="38" width="216" height="190" rx="10"/><path d="M80 192V82M80 192H240M106 181V151M148 181V122M190 181V98M232 181V76M89 110L131 87L172 68L221 54"/>'
};
const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});try{const p=await browser.newPage({viewport:{width:320,height:260}});for(const [key,drawing] of Object.entries(drawings)){const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="320" height="260" viewBox="0 0 320 260"><rect width="320" height="260" rx="20" fill="#f6f7f4"/><g fill="#d8eee2" stroke="#002a60" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">${drawing}</g></svg>`;fs.writeFileSync(new URL(key+'.svg',root),svg);await p.setContent(svg);await p.locator('svg').screenshot({path:fileURLToPath(new URL(key+'.png',root))});}console.log('Rendered7 original vector learning cues. No database writes.');}finally{await browser.close();}
