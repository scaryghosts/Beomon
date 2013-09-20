<!DOCTYPE html>                                                                                                                                                                     
<html>                                                                                                                                                                              
    <head>                                                                                                                                                                          
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">                                                                                                
        <title>{{ head_doc["_id"] }}</title>
    </head>                                                                                                                                                                         
                                                                                                                                                                                    
                                                                                                                                                                                    
                                                                                                                                                                                    
    <body>
        <h2>Node {{ head_doc["_id"] }}</h2>
        
        
        <!-- Health information -->
        <p>
        %processes_all_good = True
        %for process, state in head_doc["processes"].items():
            %if state is False:
                %processes_all_good = False
                
                <span style="color:red">{{ process }} : fail</span><br>
                
            %end
            
        %end
        
        %if processes_all_good is True:
            State: ok<br>
            
        %else:
            <span style="color:red">State: fail</span><br>
            
        %end
                
        
        <!-- Basic information of the node -->
        Class: {{ head_doc["compute_node_class"] }}<br>
        Primary of: {{ head_doc["primary_of"] }}<br>
        Secondary of: {{ head_doc["secondary_of"] }}<br>
        Last Check-in: {{ head_doc["last_check"] }}<br>
        </p>


        <!-- Mismatched files -->
        <p>
        %if len(bad_files) == 0:
            File mismatch check: ok<br>
            
        %else:
            %for each_file in bad_files:
                <span style="color:red">Does not match head0a: {{ each_file }}</span><br>
                
            %end
            
        %end
        </p>
        
        
        <!-- Zombies -->
        <p>
        Zombie Processes:</span><br>
        %if len(head_doc["zombies"]) == 0:
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;No zombies found<br>
            
        %else:
            %for zombie in head_doc["zombies"]:
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Node: {{ zombie["node"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;PID: {{ zombie["PID"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;User: {{ zombie["user"] }}<br>
                &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Command: {{ zombie["command"] }}<br>
                <br>
                
            %end
            
        %end
        </p>
    </body>
</html>
