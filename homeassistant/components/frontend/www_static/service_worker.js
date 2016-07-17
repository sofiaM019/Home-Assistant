"use strict";function deleteAllCaches(){return caches.keys().then(function(e){return Promise.all(e.map(function(e){return caches.delete(e)}))})}var PrecacheConfig=[["/","3bdc53ee7d627d4512407b623455f138"],["/frontend/panels/dev-event-f1f47bf3f0e305f855a99dd1ee788045.html","2831a46da3a8ffb1339eb4cad24f9623"],["/frontend/panels/dev-info-50a7817f60675feef3e4c9aa9a043fe1.html","92d473c7565c9dd0ee188ed96db7df6c"],["/frontend/panels/dev-service-d507e0018faf73d58a1fdeb2a0368505.html","ee7861775eeba5482b4cbcaece80c893"],["/frontend/panels/dev-state-6a4418826419f235fd9fcc5e952e858c.html","2b908b2429154b12f9550dcf6a227844"],["/frontend/panels/dev-template-cc8917fdad5a4fc81cc1d4104ea0d2dc.html","e00be617ab0d30f29a6267a3288d011d"],["/frontend/panels/map-d2cf412d52f43431307bbc2e216be9c9.html","0adb7e1753edb2c8dd288f7b0ab36eb6"],["/static/core-4783ccdb2f15d3a63fcab9be411629b7.js","c1593821e5fa766c0c9d15009daff8fb"],["/static/frontend-35a686ea968959f7e09c7d628c51a823.html","50e6a71698e1dc75e72f8bbeb71ef7f7"],["/static/mdi-a7fa9237b7da93951076b4fe26cb8cd2.html","bd484adf5c530c651d98621ece280d3a"],["static/fonts/roboto/Roboto-Bold.ttf","d329cc8b34667f114a95422aaad1b063"],["static/fonts/roboto/Roboto-Light.ttf","7b5fb88f12bec8143f00e21bc3222124"],["static/fonts/roboto/Roboto-Medium.ttf","fe13e4170719c2fc586501e777bde143"],["static/fonts/roboto/Roboto-Regular.ttf","ac3f799d5bbaf5196fab15ab8de8431c"],["static/icons/favicon-192x192.png","419903b8422586a7e28021bbe9011175"],["static/icons/favicon.ico","04235bda7843ec2fceb1cbe2bc696cf4"],["static/images/card_media_player_bg.png","a34281d1c1835d338a642e90930e61aa"],["static/webcomponents-lite.min.js","b0f32ad3c7749c40d486603f31c9d8b1"]],CacheNamePrefix="sw-precache-v1--"+(self.registration?self.registration.scope:"")+"-",IgnoreUrlParametersMatching=[/^utm_/],addDirectoryIndex=function(e,t){var a=new URL(e);return"/"===a.pathname.slice(-1)&&(a.pathname+=t),a.toString()},getCacheBustedUrl=function(e,t){t=t||Date.now();var a=new URL(e);return a.search+=(a.search?"&":"")+"sw-precache="+t,a.toString()},isPathWhitelisted=function(e,t){if(0===e.length)return!0;var a=new URL(t).pathname;return e.some(function(e){return a.match(e)})},populateCurrentCacheNames=function(e,t,a){var n={},c={};return e.forEach(function(e){var r=new URL(e[0],a).toString(),o=t+r+"-"+e[1];c[o]=r,n[r]=o}),{absoluteUrlToCacheName:n,currentCacheNamesToAbsoluteUrl:c}},stripIgnoredUrlParameters=function(e,t){var a=new URL(e);return a.search=a.search.slice(1).split("&").map(function(e){return e.split("=")}).filter(function(e){return t.every(function(t){return!t.test(e[0])})}).map(function(e){return e.join("=")}).join("&"),a.toString()},mappings=populateCurrentCacheNames(PrecacheConfig,CacheNamePrefix,self.location),AbsoluteUrlToCacheName=mappings.absoluteUrlToCacheName,CurrentCacheNamesToAbsoluteUrl=mappings.currentCacheNamesToAbsoluteUrl;self.addEventListener("install",function(e){e.waitUntil(Promise.all(Object.keys(CurrentCacheNamesToAbsoluteUrl).map(function(e){return caches.open(e).then(function(t){return t.keys().then(function(a){if(0===a.length){var n=e.split("-").pop(),c=getCacheBustedUrl(CurrentCacheNamesToAbsoluteUrl[e],n),r=new Request(c,{credentials:"same-origin"});return fetch(r).then(function(a){return a.ok?t.put(CurrentCacheNamesToAbsoluteUrl[e],a):(console.error("Request for %s returned a response status %d, so not attempting to cache it.",c,a.status),caches.delete(e))})}})})})).then(function(){return caches.keys().then(function(e){return Promise.all(e.filter(function(e){return 0===e.indexOf(CacheNamePrefix)&&!(e in CurrentCacheNamesToAbsoluteUrl)}).map(function(e){return caches.delete(e)}))})}).then(function(){"function"==typeof self.skipWaiting&&self.skipWaiting()}))}),self.clients&&"function"==typeof self.clients.claim&&self.addEventListener("activate",function(e){e.waitUntil(self.clients.claim())}),self.addEventListener("message",function(e){"delete_all"===e.data.command&&(console.log("About to delete all caches..."),deleteAllCaches().then(function(){console.log("Caches deleted."),e.ports[0].postMessage({error:null})}).catch(function(t){console.log("Caches not deleted:",t),e.ports[0].postMessage({error:t})}))}),self.addEventListener("fetch",function(e){if("GET"===e.request.method){var t=stripIgnoredUrlParameters(e.request.url,IgnoreUrlParametersMatching),a=AbsoluteUrlToCacheName[t],n="index.html";!a&&n&&(t=addDirectoryIndex(t,n),a=AbsoluteUrlToCacheName[t]);var c="/";if(!a&&c&&e.request.headers.has("accept")&&e.request.headers.get("accept").includes("text/html")&&isPathWhitelisted(["^((?!(static|api)).)*$"],e.request.url)){var r=new URL(c,self.location);a=AbsoluteUrlToCacheName[r.toString()]}a&&e.respondWith(caches.open(a).then(function(e){return e.keys().then(function(t){return e.match(t[0]).then(function(e){if(e)return e;throw Error("The cache "+a+" is empty.")})})}).catch(function(t){return console.warn('Couldn\'t serve response for "%s" from cache: %O',e.request.url,t),fetch(e.request)}))}});