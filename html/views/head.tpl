<!DOCTYPE html>                                                                                                                                                                     
<html>                                                                                                                                                                              
    <head>                                                                                                                                                                          
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">                                                                                                
        <title>{{ head_doc["_id"] }}</title>
    </head>                                                                                                                                                                         
                                                                                                                                                                                    
                                                                                                                                                                                    
                                                                                                                                                                                    
    <body>
        <h2>{{ head_doc["_id"] }}</h2>
        <p>
        Class: {{ head_doc["compute_node_class"] }}<br>
        Primary of: {{ head_doc["primary_of"] }}<br>
        Secondary of: {{ head_doc["secondary_of"] }}<br>
        Last Check-in: {{ head_doc["last_check"] }}<br>
        Processes:<br>
        %for process, value in head_doc["processes"].items():
            &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{{ process }}: {{ value }}<br>
        %end
        </p>


        <p>
        <span style="font-weight:bold">File Check:</span><br>
        %if len(bad_files) == 0:
            All checked files match head0a.<br>
        %else:
            %for each_file in bad_files:
                Does not match head0a: {{ each_file }}<br>
            %end
        %end
        </p>
        
        
        <p>
        <span style="font-weight:bold">Zombie Processes:</span><br>
        %if len(head_doc["zombies"]) == 0:
            No zombies found.
        %else:
            %for zombie in head_doc["zombies"]:
                Node: {{ zombie["node"] }}<br>
                PID: {{ zombie["PID"] }}<br>
                User: {{ zombie["user"] }}<br>
                Command: {{ zombie["command"] }}<br>
                <br>
            %end
        %end
        </p>
    </body>
</html>
