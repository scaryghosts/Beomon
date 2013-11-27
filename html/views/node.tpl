<!DOCTYPE html>                                                                                                                                                                     
<html>                                                                                                                                                                              
    <head>                                                                                                                                                                          
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">                                                                                                
        <title>Node {{ node_doc["_id"] }}</title>
        %import locale
    </head>                                                                                                                                                                         
                                                                                                                                                                                    
                                                                                                                                                                                    
                                                                                                                                                                                    
    <body>
        <h2>Node {{ node_doc["_id"] }}</h2>
        
        <!-- Health information -->
        <p>
        %if node_doc["state"] == "up":
            State: up (since {{ node_doc["state_time"] }})<br>
            
        %else:
            <span style="color:red">State: {{ node_doc["state"] }} (since {{ node_doc["state_time"] }})</span><br>
        
        %end
        
        
        %if node_doc["pbs"] is True:
            PBS: ok<br>
            
        %else:
            <span style="color:red">PBS: fail</span><br>
        
        %end
        
        
        %if node_doc["moab"] is True:
            MOAB: ok<br>
            
        %else:
            <span style="color:red">MOAB: fail</span><br>
        
        %end
        
        
        %if node_doc["infiniband"] is True:
            Infiniband: ok<br>
            
        %else:
            <span style="color:red">Infiniband: fail</span><br>
        
        %end
        
        
        %filesystems_all_good = True
        %for filesystem, state in node_doc["filesystems"].items():
            %if state is not True:
                %filesystems_all_good = False
                
                <span style="color:red">{{ filesystem }} : fail<br>
                
            %end
        %end
                
        %if filesystems_all_good is True:
            Filesystems: ok<br>
        %end
        </p>

        
        <!-- Basic information of the node -->
        <p>
        CPU:<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Type: {{ node_doc["cpu"]["cpu_type"] }}<br>
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cores: {{ node_doc["cpu"]["cpu_num"] }}<br>
        GPU:<br>
            %if node_doc["gpu"]["num_cards"] != 0:
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;GPU Type: {{ node_doc["gpu"]["gpu_type"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Cards: {{ node_doc["gpu"]["num_cards"] }}<br>
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


        <!-- Outages -->
        <p>
        <span style="font-weight:bold;">Outages:</span><br>
        %if len(outages) == 0:
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;No outages found.<br>

        %else:
            %for outage in outages:
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Down: {{ outage["down"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Up: {{ outage["up"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Duration: {{ outage["outage"] }}<br>
                <br>
            %end
        %end
        </p>
        
        
        <!-- Journal section -->
        <p>
        <span style="font-weight:bold;">Journal:</span>
        %if len(node_doc["journal"]) > 0:
            %for entry in node_doc["journal"]:
                <div style="text-align: left; max-width: 300px;">
                    <div>
                        {{ entry["time"] }}
                    </div>
                    
                    <div>
                        {{! entry["entry"] }}
                    </div>
                </div>
                <br>
            %end
            
        %else:
            <br>No journal entries<br>
        %end
        
        <br>
        <form action="/beomon/node/{{node_doc['_id']}}/journal" method="post">
            <textarea cols="75" rows="10" name="entry"></textarea><br>
            <input value="Add to journal" type="submit">
        </form>
        </p>

    </body>
</html>
