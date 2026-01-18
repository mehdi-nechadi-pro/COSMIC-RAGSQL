        let myLines; $.getJSON('/static/js_virtualsky/lines_latin.json', data => myLines = data.lines);
        var planetarium;
        let currentUserState = {
            lat: 48.8566, long: 2.3522, hour: new Date().toISOString(), city: "Localisation inconnue"
        };

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
                // Get result from the back-end
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

                const data = await response.json();
                document.querySelector(".temporary")?.remove();
                addMessage(data.reply, "bot");

                if (data.detected_city) currentUserState.city = data.detected_city;
                if (data.hour) currentUserState.hour = data.hour;
                if (data.latitude) currentUserState.lat = data.latitude;
                if (data.longitude) currentUserState.long = data.longitude;

                var constellations_names = data.constellations
                console.log(data.constellations)
                var targets = data.targets;
                if (targets && targets.length > 0) {
                    createMap(parseFloat(data.latitude), parseFloat(data.longitude), data.hour);
                    console.log(targets)
                    targets.forEach(obj => {
                        planetarium.addPointer({
                            ra: parseFloat(obj.ra), dec: parseFloat(obj.dec), label: obj.label, img: obj.url, url:" ", colour: 'orange', r: 15
                        });
                    })
                        
                } else {
                    createMap(currentUserState.lat, currentUserState.long, currentUserState.hour);
                }
                
                if (constellations_names) {
                    setTimeout(() => {
                    ShowConstellation(planetarium, constellations_names);
                    planetarium.constellation.lines = true;
                    planetarium.constellation.labels = true;
                    planetarium.draw(); }, 200);
                }

            } catch (error) {
                console.error(error);
                document.querySelector(".temporary")?.remove();
                addMessage("Erreur : " + error, "bot");
            }
        }

        function addMessage(text, className) {
            var chatDiv = document.getElementById("chat-history");
            var msgDiv = document.createElement("div");
            msgDiv.className = "msg " + className;
            msgDiv.innerHTML = text; 
            chatDiv.appendChild(msgDiv);
            chatDiv.scrollTop = chatDiv.scrollHeight;
        }

        function toggleMap() {
            document.body.classList.toggle('map-closed');
            setTimeout(() => { if (planetarium) planetarium.resize(); }, 600);
        }

        $(document).ready(function() {
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
        var constellationsState = false;

        
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

        function ShowConstellation(planetarium, constellations) {
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