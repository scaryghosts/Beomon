<!DOCTYPE html>
<html>
    <head>
        <link href="/static/style.css" media="all" rel="stylesheet" type="text/css">
        <title>{{ node_doc["_id"] }}</title>
    </head>



    <body>
        <h2>Node {{ node_doc["_id"] }}</h2>


        <!-- Health information -->
        <p>
        %processes_all_good = True
        %for process, state in node_doc["processes"].items():
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


        Load average 1 minute: {{ node_doc["loadavg"]["1"] }}<br>
        Load average 5 minutes: {{ node_doc["loadavg"]["5"] }}<br>
        Load average 15 minutes: {{ node_doc["loadavg"]["15"] }}<br>


        <!-- Basic information of the node -->
        Class: {{ node_doc["compute_node_class"] }}<br>
        Primary of: {{ node_doc["primary_of"] }}<br>
        Secondary of: {{ node_doc["secondary_of"] }}<br>
        Last Check-in: {{ node_doc["last_check"] }}<br>
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



        <!-- Journal section -->
        <p>
        <span style="font-weight:bold;">Journal:</span>
        %if len(node_doc["journal"]) > 0:
            %for entry in node_doc["journal"]:
                <div style="text-align: left; max-width: 600px;">
                    <div>
                        {{ entry["time"] }}:
                    </div>

                    <div>
                        {{! entry["entry"] }}
                    </div>
                </div>
                ----------------------------------
                <br>
            %end

        %else:
            <br>No journal entries<br>
        %end

        <br>
        New journal entry:
        <form action="/beomon/head/{{node_doc['_id']}}/journal" method="post">
            <textarea cols="75" rows="10" name="entry"></textarea><br>
            <input value="Add to journal" type="submit">
        </form>
        </p>
    </body>
</html>
