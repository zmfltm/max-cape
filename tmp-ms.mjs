import { chromium } from '@playwright/test';
const b=await chromium.launch(); const p=await b.newPage({viewport:{width:1280,height:1024},deviceScaleFactor:1});
await p.goto('file:///home/chris/projects/mudkip/stars.html',{waitUntil:'load'});
await p.waitForTimeout(2500);
const st = await p.evaluate(()=>({status: document.getElementById('starstatus')?.textContent,
  frame: !!document.querySelector('.starframe'), overlay: !!document.querySelector('.fover'),
  note: document.querySelector('.starnone')?.textContent?.slice(0,60),
  dupLede: document.body.innerText.split('Crashed stars land').length-1,
  iframePE: document.querySelector('.starframe iframe') ? getComputedStyle(document.querySelector('.starframe iframe')).pointerEvents : null}));
console.log(JSON.stringify(st));
await p.locator('#stars').screenshot({path:'/tmp/mudkip-embed.png'});
await b.close();
