"use strict";function setOfCachedUrls(e){return e.keys().then(function(e){return e.map(function(e){return e.url})}).then(function(e){return new Set(e)})}function notificationEventCallback(e,t){firePushCallback({action:t.action,data:t.notification.data,tag:t.notification.tag,type:e},t.notification.data.jwt)}function firePushCallback(e,t){delete e.data.jwt,0===Object.keys(e.data).length&&e.data.constructor===Object&&delete e.data,fetch("/api/notify.html5/callback",{method:"POST",headers:new Headers({"Content-Type":"application/json",Authorization:"Bearer "+t}),body:JSON.stringify(e)})}var precacheConfig=[["/","78ea41075e1cab2bdc72e474bc905291"],["/frontend/panels/dev-event-4886c821235492b1b92739b580d21c61.html","0f16df49a7d965ddc1fd55f7bd3ffd3f"],["/frontend/panels/dev-info-24e888ec7a8acd0c395b34396e9001bc.html","7bb116813e8dbab7bcfabdf4de3ec83f"],["/frontend/panels/dev-service-ac2c50e486927dc4443e93d79f08c06e.html","1daf8c159d2fab036f7094b0e737f1a0"],["/frontend/panels/dev-state-8f1a27c04db6329d31cfcc7d0d6a0869.html","002ea95ab67f5c06f9112008a81e571b"],["/frontend/panels/dev-template-82cd543177c417e5c6612e07df851e6b.html","81c4dbc540739dcf49c351cf565db71b"],["/frontend/panels/map-d3dae1400ec4e4cd7681d2aa79131d55.html","19102e8bcbe3735db7358068b17f323a"],["/static/compatibility-8e4c44b5f4288cc48ec1ba94a9bec812.js","4704a985ad259e324c3d8a0a40f6d937"],["/static/core-d4a7cb8c80c62b536764e0e81385f6aa.js","37e34ec6aa0fa155c7d50e2883be1ead"],["/static/frontend-a7d4cb8260e8094342b5bd8c36c4bf5b.html","73343b5bed6f016b2ba7ff8ee4a1e219"],["/static/mdi-c92bd28c434865d6cabb34cd3c0a3e4c.html","7e24a0584d139fef75d7678ef3c3b008"],["static/fonts/roboto/Roboto-Bold.ttf","d329cc8b34667f114a95422aaad1b063"],["static/fonts/roboto/Roboto-Light.ttf","7b5fb88f12bec8143f00e21bc3222124"],["static/fonts/roboto/Roboto-Medium.ttf","fe13e4170719c2fc586501e777bde143"],["static/fonts/roboto/Roboto-Regular.ttf","ac3f799d5bbaf5196fab15ab8de8431c"],["static/icons/favicon-192x192.png","419903b8422586a7e28021bbe9011175"],["static/icons/favicon.ico","04235bda7843ec2fceb1cbe2bc696cf4"],["static/images/card_media_player_bg.png","a34281d1c1835d338a642e90930e61aa"],["static/webcomponents-lite.min.js","32b5a9b7ada86304bec6b43d3f2194f0"]],cacheName="sw-precache-v3--"+(self.registration?self.registration.scope:""),ignoreUrlParametersMatching=[/^utm_/],addDirectoryIndex=function(e,t){var n=new URL(e);return"/"===n.pathname.slice(-1)&&(n.pathname+=t),n.toString()},cleanResponse=function(e){return e.redirected?("body"in e?Promise.resolve(e.body):e.blob()).then(function(t){return new Response(t,{headers:e.headers,status:e.status,statusText:e.statusText})}):Promise.resolve(e)},createCacheKey=function(e,t,n,a){var c=new URL(e);return a&&c.pathname.match(a)||(c.search+=(c.search?"&":"")+encodeURIComponent(t)+"="+encodeURIComponent(n)),c.toString()},isPathWhitelisted=function(e,t){if(0===e.length)return!0;var n=new URL(t).pathname;return e.some(function(e){return n.match(e)})},stripIgnoredUrlParameters=function(e,t){var n=new URL(e);return n.search=n.search.slice(1).split("&").map(function(e){return e.split("=")}).filter(function(e){return t.every(function(t){return!t.test(e[0])})}).map(function(e){return e.join("=")}).join("&"),n.toString()},hashParamName="_sw-precache",urlsToCacheKeys=new Map(precacheConfig.map(function(e){var t=e[0],n=e[1],a=new URL(t,self.location),c=createCacheKey(a,hashParamName,n,!1);return[a.toString(),c]}));self.addEventListener("install",function(e){e.waitUntil(caches.open(cacheName).then(function(e){return setOfCachedUrls(e).then(function(t){return Promise.all(Array.from(urlsToCacheKeys.values()).map(function(n){if(!t.has(n)){var a=new Request(n,{credentials:"same-origin"});return fetch(a).then(function(t){if(!t.ok)throw new Error("Request for "+n+" returned a response with status "+t.status);return cleanResponse(t).then(function(t){return e.put(n,t)})})}}))})}).then(function(){return self.skipWaiting()}))}),self.addEventListener("activate",function(e){var t=new Set(urlsToCacheKeys.values());e.waitUntil(caches.open(cacheName).then(function(e){return e.keys().then(function(n){return Promise.all(n.map(function(n){if(!t.has(n.url))return e.delete(n)}))})}).then(function(){return self.clients.claim()}))}),self.addEventListener("fetch",function(e){if("GET"===e.request.method){var t,n=stripIgnoredUrlParameters(e.request.url,ignoreUrlParametersMatching);t=urlsToCacheKeys.has(n);t||(n=addDirectoryIndex(n,"index.html"),t=urlsToCacheKeys.has(n));!t&&"navigate"===e.request.mode&&isPathWhitelisted(["^((?!(static|api|local|service_worker.js|manifest.json)).)*$"],e.request.url)&&(n=new URL("/",self.location).toString(),t=urlsToCacheKeys.has(n)),t&&e.respondWith(caches.open(cacheName).then(function(e){return e.match(urlsToCacheKeys.get(n)).then(function(e){if(e)return e;throw Error("The cached response that was expected is missing.")})}).catch(function(t){return console.warn('Couldn\'t serve response for "%s" from cache: %O',e.request.url,t),fetch(e.request)}))}}),self.addEventListener("push",function(e){var t;e.data&&(t=e.data.json(),e.waitUntil(self.registration.showNotification(t.title,t).then(function(e){firePushCallback({type:"received",tag:t.tag,data:t.data},t.data.jwt)})))}),self.addEventListener("notificationclick",function(e){var t;notificationEventCallback("clicked",e),e.notification.close(),e.notification.data&&e.notification.data.url&&(t=e.notification.data.url)&&e.waitUntil(clients.matchAll({type:"window"}).then(function(e){var n,a;for(n=0;n<e.length;n++)if(a=e[n],a.url===t&&"focus"in a)return a.focus();if(clients.openWindow)return clients.openWindow(t)}))}),self.addEventListener("notificationclose",function(e){notificationEventCallback("closed",e)});