<!DOCTYPE html>                                                                                                                                                                     
<html>                                                                                                                                                                              
    <head>                                                                                                                                                                          
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">                                                                                                
        <title>Node {{ node_doc["_id"] }}</title>
        %import locale
    </head>                                                                                                                                                                         
                                                                                                                                                                                    
                                                                                                                                                                                    
                                                                                                                                                                                    
    <body>
        <h2>Node {{ node_doc["_id"] }}</h2>
        <p>
        CPU:<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Type: {{ node_doc["cpu"]["cpu_type"] }}<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cores: {{ node_doc["cpu"]["cpu_num"] }}<br>
        GPU:<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cards: {{ node_doc["gpu"]["num_cards"] }}<br>
            %if node_doc["gpu"]["num_cards"] != 0:
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total RAM Size: {{ node_doc["gpu"]["ram_size"] }} GB<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Total GPU Cores: {{ node_doc["gpu"]["num_cores"] }}<br>
            %end
        IPs:<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;GigE IP: {{ node_doc["ip"]["gige"] }}<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;BMC IP: {{ node_doc["ip"]["bmc"] }}<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;IB IP: {{ node_doc["ip"]["ib"] }}<br>
        RAM: {{ node_doc["ram"] }} GB<br>
        Scratch Size: {{ node_doc["scratch_size"] }} GB<br>
        Rack: {{ node_doc["rack"]}}<br>
        Serial: {{ node_doc["serial"] }}<br>
        Last Check-in: {{ node_doc["last_check"] }}<br>
        </p>



        <p>
        <span style="font-weight:bold">Outages:</span><br>
        %if len(outages) == 0:
            No outages found.</p>

        %else:
            %for outage in outages:
                Down: {{ outage["down"] }}<br>
                Up: {{ outage["up"] }}<br>
                Duration: {{ outage["outage"] }}<br>
                <br>
            %end
        %end
        </p>

    </body>
</html>
