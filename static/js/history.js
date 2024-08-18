function getStartTime(delta) {
    var start = new Date();
    start.setHours(start.getHours() - delta);
    let year = start.getUTCFullYear();
    let month = start.getUTCMonth();
    if (month < 10)
        month = "0" + (month + 1);
    let day = start.getUTCDate();
    if (day < 10)
        day = "0" + day;
    let hour = start.getUTCHours();
    if (hour < 10)
        hour = "0" + hour;
    let minute = start.getUTCMinutes();
    if (minute < 10)
        minute = "0" + minute;
    let startString = '' + year + month + day + '_' + hour + ':' + minute + ':00';
    return startString;
}

function initializeCombobox(jsonData) {
    const pondSelector = document.getElementById('pondSelector');
    pondSelector.innerHTML = '<option value="all" selected>All Ponds</option>'; // Default option

    // Extract pond numbers and sort them
    const pondNumbers = jsonData.features.map(feature => feature.properties.number).sort((a, b) => a - b);

    // Append sorted pond numbers to the combobox
    pondNumbers.forEach(pondId => {
        const option = document.createElement('option');
        option.value = pondId;
        option.textContent = `Pond ${pondId}`;
        pondSelector.appendChild(option);
    });
}

function generateTable(data) {
    const tableBody = document.getElementById('data-table-body');
    tableBody.innerHTML = ''; // Clear existing rows
    const now = moment();

    data.forEach(item => {
        const row = tableBody.insertRow();
        // const isRecent = moment(item.datetime).isAfter(now.subtract(60, 'seconds'));
        // item.datetime.toIsoString().slice(0, 19).replace('T', ' ')
        row.innerHTML = `
            <td>${item.datetime.toISOString().slice(5, 10) + '-' + item.datetime.toLocaleTimeString()}</td>
            <td>${item.pond_id}</td>
            <td>${item.avg_do.toFixed(2)}</td>
            <td>${item.avg_temp.toFixed(2)}</td>
            <td>${item.avg_pressure.toFixed(2)}</td>
            <td>${item.location}</td>
            <td>${item.type}</td>
        `;

        // if (isRecent) {
        //     row.style.color = 'red';
        // }
    });

    document.getElementById('pageInfo').innerText = `Page ${currentPage} of ${Math.ceil(paginatedData.length / rowsPerPage)}`;
    document.getElementById('prevBtn').disabled = currentPage === 1;
    document.getElementById('nextBtn').disabled = currentPage === Math.ceil(paginatedData.length / rowsPerPage);
}


function displayPage(page) {
    const startIndex = (page - 1) * rowsPerPage;
    const endIndex = page * rowsPerPage;
    const currentData = paginatedData.slice(startIndex, endIndex);

    generateTable(currentData);
}

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        displayPage(currentPage);
    }
}

function nextPage() {
    if (currentPage * rowsPerPage < paginatedData.length) {
        currentPage++;
        displayPage(currentPage);
    }
}

function transformData(jsonDatas, pondId) {
    const data = [];
    let i;

    for (i=0;i<jsonDatas.length;i++){
        const jsonData = jsonDatas[i];
        if (jsonData === null) {
            continue;
        }
            
        Object.keys(jsonData).forEach(key => {
            const [date, time] = key.split('_');
            const year = date.substring(0, 4);
            const month = date.substring(4, 6) - 1;
            const day = date.substring(6, 8);
            const hour = time.substring(0, 2);
            const min = time.substring(3, 5);
            const sec = time.substring(6, 8);
            const datetime = new Date(Date.UTC(year, month, day, hour, min, sec));
            const location = jsonData[key].lat + ", " + jsonData[key].lng;

            // Ensure `jsonData[key].do` is an array of floats
            const doValues = Array.isArray(jsonData[key].do) 
                ? jsonData[key].do.map(value => parseFloat(value)) 
                : [parseFloat(jsonData[key].do)];
            const halfDoValues = doValues.slice(Math.ceil(doValues.length / 2), doValues.length);
            const avg_do = halfDoValues.reduce((sum, current) => sum + (isNaN(current) ? 0 : current), 0) * 100 / halfDoValues.length / jsonData[key].init_do;

            const pressureValues = Array.isArray(jsonData[key].pressure) 
                ? jsonData[key].pressure.map(value => parseFloat(value)) 
                : [parseFloat(jsonData[key].pressure)];

            const avg_pressure = pressureValues.reduce((sum, current) => sum + (isNaN(current) ? 0 : current), 0) / pressureValues.length;

            const tempValues = Array.isArray(jsonData[key].temp) 
                ? jsonData[key].temp.map(value => parseFloat(value)) 
                : [parseFloat(jsonData[key].temp)];
            const halfTempValues = tempValues.slice(Math.ceil(tempValues.length / 2), tempValues.length);
            const avg_temp = 35 + 9 / 5 * halfTempValues.reduce((sum, current) => sum + (isNaN(current) ? 0 : current), 0) / halfTempValues.length;

            const entry = {
                datetime,
                do: doValues,
                avg_do: avg_do,
                drone_id: jsonData[key].drone_id,
                init_do: jsonData[key].init_do,
                init_pressure: jsonData[key].init_pressure,
                location: location,
                pond_id: jsonData[key].pid,
                pressure: pressureValues,
                avg_pressure: avg_pressure,
                temp: tempValues,
                avg_temp: avg_temp,
                type: jsonData[key].type,
            };
            //TODO: temporary fix for GPS mode on Topside
            if (entry['type'] == undefined){
                entry['pond_id'] = 'gps';
                entry['type'] = 'gps';
            }
            // console.log(entry);
            data.push(entry);
        });
    }

    // Sort the data from latest to oldest
    data.sort((a, b) => b.datetime - a.datetime);
    
    if (pondId !== 'all') {
        return data.filter(item => item.pond_id === pondId);
    }
    return data;
}