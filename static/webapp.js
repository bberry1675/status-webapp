const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function getColumnDates() {
    let dates = []
    let currDate = new Date();
    currDate.setMonth(currDate.getMonth() - 6);
    for (let i = 1; i <= 13; i++) {
        dates.push(`01 ${months[currDate.getMonth()]} ${currDate.getFullYear()} 00:00:00 GMT`);
        currDate.setMonth(currDate.getMonth() + 1);
    }
    dates = dates.map(value => {
        return luxon.DateTime.fromRFC2822(value, { setZone: true })
    })
    return dates;
}


function generateRow(clientName, status_obj) {
    let client_status = status_obj.filter(value => {
        return clientName == value[1]
    }).map(value => {
        let retValue = value
        // console.log(retValue[2])
        retValue[2] = luxon.DateTime.fromRFC2822(retValue[2], { setZone: true })
        return retValue
    });
    console.log(client_status)

    let columnDates = getColumnDates();

    let retValue = `<tr><th scope="row">${clientName}</th>`;
    for (let i = 0; i < 13; i++) {
        let currentCol = columnDates[i];
        // console.log(client_status[0][2])
        // console.log(currentCol)
        let current_col_status = client_status.filter(value => value[2].equals(currentCol))
        if (current_col_status.length > 0) {
            console.log("found a status for: " + clientName)
            switch (current_col_status[0][3]) {
                case 0: retValue += `<td style="padding-left:0px;padding-right:0px"><select prime_key=${current_col_status[0][0]} class="form-control form-control-sm min-select"><option selected value="nostatus">No Status</option><option value="progress">In Progress</option><option value="complete">Completed</option></select></td>`; break;
                case 1: retValue += `<td style="padding-left:0px;padding-right:0px"><select prime_key=${current_col_status[0][0]} class="form-control form-control-sm min-select"><option value="nostatus">No Status</option><option selected value="progress">In Progress</option><option value="complete">Completed</option></select></td>`; break;
                case 2: retValue += `<td style="padding-left:0px;padding-right:0px"><select prime_key=${current_col_status[0][0]} class="form-control form-control-sm min-select"><option value="nostatus">No Status</option><option value="progress">In Progress</option><option selected value="complete">Completed</option></select></td>`; break;
                default: break;
            }
        }
        else {
            console.log("Did not find any status for " + clientName)
            retValue += `<td style="padding-left:0px;padding-right:0px"><select post_body=${JSON.stringify({client_name: clientName, year: currentCol.get('year'), month: currentCol.get('month')})} class="form-control form-control-sm min-select"><option value="nostatus">No Status</option><option value="progress">In Progress</option><option value="complete">Completed</option></select></td>`;
        }
    }
    retValue += '</tr>';
    return retValue;
}

function generateHeaderDates() {
    let date = new Date();
    let retValue = "";
    for (let i = 6; i > 0; i--) {
        retValue += `<th scope="col">${months[(date.getMonth() - i) < 0 ? (12 + (date.getMonth() - i)) : date.getMonth() - i]}</th>`;
    }
    retValue += `<th scope="col">${months[date.getMonth()]}(Today)</th>`;
    for (let i = 1; i < 7; i++) {
        retValue += `<th scope="col">${months[(date.getMonth() + i) % 12]}</th>`
    }
    return retValue;
}

function getClientNames() {
    let requestsettings = {
        url: '/api/v1/clients'
    }

    $.ajax(requestsettings).done(function (data) {
        console.log(data);
    });

}


function createStatusTable() {
    //create the header of the table
    $('#table-header').append(generateHeaderDates());

    $.get('/api/v1/clients', function (client_names, status) {
        //data is a list of strings for all the client names
        let starting_date = new Date()
        let ending_date = new Date()

        starting_date.setMonth(starting_date.getMonth() - 6)
        ending_date.setMonth(ending_date.getMonth() + 6)

        get_status_body = {
            clients: client_names,
            starting_year: starting_date.getFullYear(),
            starting_month: starting_date.getMonth() + 1,
            ending_year: ending_date.getFullYear(),
            ending_month: ending_date.getMonth() + 1
        }

        get_status_settings = {
            url: 'http://' + window.location.host + '/api/v1/clients/status',
            contentType: 'application/json',
            data: get_status_body
        }

        $.ajax(get_status_settings).done(function (client_status) {
            // console.log(client_status);

            let rows = client_names.map(value => {
                return generateRow(value, client_status);
            })

            rows.forEach(value => { $('#table-body').prepend(value) });

            $('select').each((index, element) => {
                let ele = $(element);
                switch (ele.find(':selected').val()) {
                    case 'nostatus': ele.css('background-color', 'lightgrey'); break;
                    case 'progress': ele.css('background-color', 'lightyellow'); break;
                    case 'complete': ele.css('background-color', 'lightgreen'); break;
                    default: break;
                }
            });

            $('select').change(event => {
                // console.log($(event.target).find(':selected').val());
                let target = $(event.target);
                let prime_key = target.attr('prime_key')
                let post_body
                if(prime_key){
                    post_body = {
                        prime_key: prime_key
                    }
                }
                else{
                    post_body= JSON.parse(target.attr('post_body'))
                }
                //console.log(post_body)
                switch (target.find(':selected').val()) {
                    case 'nostatus': target.css('background-color', 'lightgrey'); post_body.status = 0; break;
                    case 'progress': target.css('background-color', 'lightyellow'); post_body.status = 1; break;
                    case 'complete': target.css('background-color', 'lightgreen'); post_body.status=2; break;
                    default: break;
                }

                // $.post('/api/v1/client', post_body, function(data){
                 
                //     console.log(data);
                // })

                let post_status_update = {
                    url: 'http://' + window.location.host + '/api/v1/client',
                    type: 'POST',
                    contentType: 'application/json',
                    data: JSON.stringify(post_body)
                }
                $.ajax(post_status_update).done(data => console.log(data))

            });
        })
    })
}