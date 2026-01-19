    let myLines; $.getJSON('/static/js_virtualsky/lines_latin.json', data => myLines = data.lines); // All constellations lines 
    var planetarium;
    var constellationsState = false;
    let currentUserState = {
        lat: 48.8566, long: 2.3522, hour: new Date().toISOString(), city: "Localisation inconnue", local_hour: new Date().toString()
    };
    let targets = {}

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
        });
    }
    async function sendChat() {
        var inputField = document.getElementById("userMsg");
        var text = inputField.value.trim();
        if (!text) return;

        addMessage(text, "user");
        inputField.value = "";
        addMessage("Recherche en cours...", "bot temporary");

        try {
            // Send Initial State
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    message: text, 
                    city: currentUserState.city, 
                    hour: currentUserState.hour, 
                    latitude: currentUserState.lat, 
                    longitude: currentUserState.long
                    })
                });
            
            // Get result from the back-end
            const data = await response.json();
            document.querySelector(".temporary")?.remove();
            addMessage(data.reply, "bot", data.targets);

            if (data.detected_city) currentUserState.city = data.detected_city;
            if (data.hour) currentUserState.hour = data.hour;
            if (data.latitude) currentUserState.lat = data.latitude;
            if (data.longitude) currentUserState.long = data.longitude;
            if (data.local_hour) currentUserState.local_hour = data.local_hour;

            Update_info_box(data.detected_city, data.local_hour, data.latitude, data.longitude)

            var constellations_names = data.constellations
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
                
            if (constellations_names) {
                setTimeout(() => {
                ShowConstellation(planetarium, constellations_names);
                planetarium.constellation.lines = true;
                planetarium.constellation.names = true;
                planetarium.draw(); }, 200);
            }

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

    function Update_info_box(city, local_hour, lat, lon) {
        
        document.getElementById("city-display").innerText = "City : " + city;
        document.getElementById("local-time-display").innerText = "Local Hour : " + local_hour ;
        document.getElementById("latitude-longitude-display").innerText = "Lat/Lon : " + lat + " / " + lon;
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

    function toggleConstellation(btnElement){ 
        console.log(planetarium)
        console.log("ToggleConstellation bool : ", constellationsState)
        if (!planetarium) return;
        constellationsState = !constellationsState

        if (planetarium.constellation) {
            planetarium.constellation.lines = constellationsState; 
            planetarium.constellation.labels = constellationsState;
        }
        planetarium.draw(); 

        if (constellationsState) {
        btnElement.classList.add('active'); 
        btnElement.style.opacity = "1";
        } else {
            btnElement.classList.remove('active'); 
            btnElement.style.opacity = "0.5";
        }
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
        // On garde le conteneur parent pour la grille
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

$(document).ready(function() { // Initial Map created based on the localisation retrieved by the nav

    // liftCurtain()
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            (position) => {
                currentUserState.lat = position.coords.latitude;
                currentUserState.long = position.coords.longitude;
                createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
            }, 
            (error) => {
                createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
            }
        );
    } else {
        createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
    }
});