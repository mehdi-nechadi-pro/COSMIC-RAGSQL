    let myLines; $.getJSON('/static/js_virtualsky/lines_latin.json', data => myLines = data.lines); // All constellations lines 
    var planetarium;
    var constellationsState = false;
    let currentUserState = {
        lat: 48.8566, 
        long: 2.3522, 
        hour: new Date().toISOString(), // UTC Strict
        city: "Paris",
        local_hour: new Date().toISOString()
    };
    let targets = {}
    let conversationHistory = [];

    function createMap(lat, long, hourString) {
        let dateObj = new Date(hourString);
        $('#starmap').empty();
        
        planetarium = $.virtualsky({
            id: 'starmap',
            projection: 'stereo',
            ground: true,
            atmosphere: true,
            fullsky: true, 
            latitude: parseFloat(lat),
            longitude: parseFloat(long),
            live: true, 
            showstars: true,
            showgalaxy: true,
            constellations: constellationsState,
            constellationlabels: constellationsState,
            starsdeep: true,
            keyboard: false,
            meteorshowers: true,
            clock: dateObj,
            showdate: false,
            showposition: false,
        });
    }
    async function sendChat() {
        var inputField = document.getElementById("userMsg");
        var text = inputField.value.trim();
        conversationHistory.push({ role: "user", content: text });
        if (!text) return;

        addMessage(text, "user");
        inputField.value = "";
        addMessage("Recherche en cours...", "bot temporary");

        try {
            console.log("Envoi : ", currentUserState)
            // Send Initial State
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: text, 
                    city: currentUserState.city, 
                    hour: currentUserState.hour, 
                    latitude: currentUserState.lat, 
                    longitude: currentUserState.long,
                    history: conversationHistory,
                    })
                });
            
            // Get result from the back-end
            const data = await response.json();
            document.querySelector(".temporary")?.remove();
            addMessage(data.reply, "bot", data.targets);
            conversationHistory.push({ role: "ai", content: data.reply });
            
            // Update currentUserState
            if (data.detected_city) currentUserState.city = data.detected_city;
            if (data.hour) currentUserState.hour = data.hour;
            if (data.latitude) currentUserState.lat = data.latitude;
            if (data.longitude) currentUserState.long = data.longitude;
            if (data.local_hour) currentUserState.local_hour = data.local_hour;
            
            console.log("Reception : ",currentUserState)

            // Update Date/Hour/Location on the map
            Update_info_box(data.detected_city, data.hour,  data.local_hour, data.latitude, data.longitude)
            
            // Create the Map and add the targets pointers
            var constellations_names = data.constellations
            console.log(constellations_names)
            var targets = data.targets;
            if (targets && targets.length > 0) {
                createMap(parseFloat(data.latitude), parseFloat(data.longitude), data.hour);
                // console.log(targets)
                targets.forEach(obj => {
                    planetarium.addPointer({
                        ra: parseFloat(obj.ra), dec: parseFloat(obj.dec), label: obj.name, img: obj.url, url:" ", colour: 'orange', r: 15
                        });
                })
                        
            } else {
                createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
            }
            
            // We show the constellations
            if (constellations_names) {
                setTimeout(() => {
                ShowConstellation(planetarium, constellations_names);
                planetarium.constellation.lines = true;
                planetarium.constellation.names = true;
                planetarium.constellation.labels = true;
                planetarium.draw(); }, 200);
            }

            // Show the Map
            liftCurtain()

            } catch (error) {
                console.error(error);
                document.querySelector(".temporary")?.remove();
                addMessage("Erreur : " + error, "bot");
            }
        }

    function addMessage(text, className, _targets = {}) {
        console.log("TARGET : ", targets)
        var chatDiv = document.getElementById("chat-history");
        var msgDiv = document.createElement("div");
        var objDiv = document.createElement("div");
        targets = _targets

        if (Object.keys(targets).length === 0) { // If targets is null we return the reply component 
            msgDiv.className = "msg " + className;
            msgDiv.innerHTML = text; 
        } else { // We create cards components for the target objects
            msgDiv.className = "msg " + className;
            msgDiv.innerHTML = text
            objDiv.innerHTML += targets_to_card(targets)
        }

        chatDiv.appendChild(msgDiv);
        chatDiv.appendChild(objDiv)

        document.querySelectorAll(".card").forEach(card => {
            card.addEventListener("click", () => {  //Open the card clicked
            console.log("Name ; ", card)
            const name = card.dataset.name;
            openCardDetails(name); });
        });

    }

    function Update_info_box(city, utc_hour, local_hour, lat, lon) {
        console.log("UTC : ", utc_hour, " LOCAL : ", local_hour)
        document.getElementById("city-display").innerText = city;
        document.getElementById("latitude-longitude-display").innerText = formatCoords(lat,lon)
        document.getElementById("local-time-display").innerText =formatAstroDateStrict(local_hour, utc_hour);
    }

    function formatCoords(lat, lon) {
        const latitude = parseFloat(lat);
        const longitude = parseFloat(lon);

        const latDir = latitude >= 0 ? 'N' : 'S';
        const lonDir = longitude >= 0 ? 'E' : 'W';

        return `${Math.abs(latitude).toFixed(2)}°${latDir}, ${Math.abs(longitude).toFixed(2)}°${lonDir}`; 
    }

    function formatAstroDateStrict(isoString, utcString) {

        if (!isoString || !isoString.includes('T')) return "Date inconnue";
        console.log("Avant : ", isoString)
        // isoString ex: "2026-01-20T14:29:00.070122+03:00"
        const parts = isoString.split('T');
        const dateRaw = parts[0]; 
        const timeRaw = parts[1]; 

        const months = ["janvier", "février", "mars", "avril", "mai", "juin", 
                        "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
        const dateParts = dateRaw.split('-');
        const year = dateParts[0];
        const month = months[parseInt(dateParts[1]) - 1];
        const day = parseInt(dateParts[2]);

        const timePart = timeRaw.substring(0, 5).replace(':', 'h'); // "14h29"

        final_format = `${day} ${month} ${year} : ${timePart}`

        const offsetMatch = utcString ? utcString.match(/([+-])(\d{2}):\d{2}$/) : null;
        if (offsetMatch) {
            final_format += ` (${offsetMatch[1]}${parseInt(offsetMatch[2])})`;
        } else if (utcString && utcString.endsWith('Z')) {
            final_format += ` (+0)`; // Format UTC Zulu
        }
        return final_format
    }

    function liftCurtain() {
        const overlay = document.getElementById('map-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            setTimeout(() => overlay.remove(), 500);
        }
    }
    
    function changeView(mode) {
        let newMag;
        let newBg;

        switch(mode) {
            case 'city':
                newMag = 3.5; 
                newBg = 'rgba(20, 20, 40, 1)'; 
                break;
                
            case 'hybrid':
                newMag = 5.0;
                newBg = 'rgba(10, 10, 15, 1)';
                break;
                
            case 'dark':
                newMag = 7.0;
                newBg = 'black';
                break;
        }
        planetarium.magnitude = newMag;
        
        const container = document.getElementById('starmap'); 
        if(container) container.style.backgroundColor = newBg;

        planetarium.draw(); 
    }

    function toggleFullscreen() {
        const mapContainer = document.getElementById('map-container');
        const btn = document.getElementById('toggleMapBtn');
        
        mapContainer.classList.toggle('fullscreen');
        
        if (planetarium) planetarium.resize();

        if (mapContainer.classList.contains('fullscreen')) {
            btn.innerHTML = "⤓";
        } else {
            btn.innerHTML = "⤢"; 
        }
    }

    function ShowConstellation(planetarium, constellations) { // show the constellations returned in constellations_IAU by the GraphAgent 
        let constellations_lines = []

        for (let i =0; i<myLines.length; i++) {
            for (let y =0; y<constellations.length; y++) {
                let constellation_line = myLines[i]
                let name = myLines[i][0]

                if(name == constellations[y]) {
                    constellations_lines.push(constellation_line)
                }
            }
        }
        planetarium.lines = constellations_lines
    }

    function targets_to_card(targets){
        let fullHtml = '<div class="astro-grid-container">';
        
        targets.forEach((result) => { 
            const content = `
            <div class="card" data-name="${result.name}">
                <div class="card-badge">${result.type}</div>
                <img src="${result.url}" class="cardImage" alt="${result.name}">
                <div class="card-body">
                    <span class="card-title">${result.name}</span>
                    <span class="card-subtitle">${parseFloat(result.ra).toFixed(2)} / ${parseFloat(result.dec).toFixed(2)}</span>
                </div>
            </div>`;
            
            fullHtml += content;
        });
        
        fullHtml += '</div>';
        return fullHtml;
    }

    function openCardDetails(label) {
        let searchName = (typeof label === 'object') ? label.name : label;
        
        console.log("On cherche : ", searchName);
        const target = targets.find(t => t.name === searchName);
        console.log("Target trouvé : ", target);

        if (!target) return; 

        const html = `
        <div class="detail-header-img" style="background-image: url('${target.url}');">
            <button class="close-btn-round" id="btnClose">×</button>
        </div>

        <div class="detail-content">
            <h2 class="detail-title">${target.name} - ${target.type || 'Objet Céleste'}</h2>
            
            <div class="detail-badges">
                <span class="badge-pill badge-blue">${target.type || 'Galaxie'}</span>
                <span class="badge-pill badge-green">👁 Visible maintenant</span>
            </div>

            <span class="desc-label">DESCRIPTION</span>
            <p class="desc-text">
                Description prochainement écrite via le RAG pour l'objet ${target.name}. 
            </p>

            <div class="info-grid">
                <div class="info-box">
                    <div class="info-icon">📍</div>
                    <div class="info-data">
                        <h4>Constellation</h4>
                        <span>${target.constellation || 'Inconnue'}</span>
                    </div>
                </div>

                <div class="info-box">
                    <div class="info-icon">⭐</div>
                    <div class="info-data">
                        <h4>Magnitude</h4>
                        <span>${target.magnitude}</span> </div>
                </div>

                <div class="info-box">
                    <div class="info-icon">🚀</div>
                    <div class="info-data">
                        <h4>RA/DEC</h4>
                        <span>${ Math.round(target.ra * 100) / 100}, ${Math.round(target.dec * 100) / 100}</span> </div>
                </div>

                <div class="info-box">
                    <div class="info-icon">📅</div>
                    <div class="info-data">
                        <h4>Catalogue</h4>
                        <span>${target.catalogue} </span> </div>
                </div>
            </div>

            <div class="action-buttons">
                <button id="btnLocate" class="btn-big btn-primary">Localiser dans le ciel</button>
            </div>
        </div>
        `;

        const panel = document.getElementById("detailsPanel");
        const content = document.getElementById("detailsContent");

        content.innerHTML = html;
        panel.style.display = "block";

        document.getElementById("btnLocate").onclick = () => {
            highlightTarget(target.name);
            panel.style.display = "none"; 
        };

        document.getElementById("btnClose").onclick = () => {
            panel.style.display = "none";
        };
    }

    // Highlight the target pointer 
    function highlightTarget(targetLabel) {
        console.log(targetLabel)
        if (!planetarium) return;

        planetarium.pointers.forEach(pointer => {
            if (pointer.label === targetLabel) {
                pointer.colour = 'red';       
                pointer.c = 'red';            
                pointer.r = 20;               
            } 
            else {
                pointer.colour = 'orange';   
                pointer.c = 'orange';
                pointer.r = 6;       
            }
        });

        planetarium.draw();

    }

    async function getCityFromLatLonJS(lat, lon) {
        const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`;

        try {
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'MonAppAstro/1.0' 
                }
            });
            
            if (!response.ok) throw new Error("Erreur API");

            const data = await response.json();
            const address = data.address || {};

            return address.city || address.town || address.village || "Lieu Inconnu";

        } catch (error) {
            console.warn("Erreur Reverse Geocoding :", error);
            return null; 
        }
    }

$(document).ready(function() { 

    function unlockInterface(cityName) {
        currentUserState.city = cityName;
        
        // createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
        
        Update_info_box(
            currentUserState.city, 
            currentUserState.hour, 
            currentUserState.local_hour, 
            currentUserState.lat, 
            currentUserState.long
        );
    }

    // We fetch the location via the navigator (If the User is fast -> it takes currentUserState (by default Paris))
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                console.log("📍 Position trouvée :", position.coords.latitude, position.coords.longitude);
                
                currentUserState.lat = position.coords.latitude;
                currentUserState.long = position.coords.longitude;
                
                let city = await getCityFromLatLonJS(currentUserState.lat, currentUserState.long)
                unlockInterface(city); 
            }, 
            (error) => {
                console.warn("⚠️ Échec GPS ou refus user. Fallback sur Paris.");
                unlockInterface("Paris (Par défaut)");
            },
            { timeout: 10000 } // Important : abandonne si le GPS met plus de 10s
        );
    } else {
        // Pas de support
        unlockInterface("Paris (GPS non supporté)");
    }
});