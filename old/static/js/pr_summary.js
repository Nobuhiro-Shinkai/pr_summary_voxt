    const pr_summary = {
    init:function() {
        pr_summary.canceled = false;
        pr_summary.requestId = "";
        pr_summary.access_token = null;
        pr_summary.testmode = {};
        pr_summary.timeoutID = -1;

        pr_summary.reset();

        

        $("#showtext").change(function() {
            let showtype = $(this).val();
            pr_summary.logs["resummarize"].redrawText(showtype == 'showtext-diff');
        });

        $(".summarize_button").on("click", function() {
            pr_summary.getSummary();
        });

        $('.prompt_button').on("click", function() {
            const prompt = $(this).data('prompt');
            $("#prompt").val(prompt);
        });

        let text = $("#targettext").val();
        if (text.trim().length == 0) {
            $(".summarize_button").prop("disabled", true);
        }
        $("#targettext,#prompt").keydown(function (e) {
            if (pr_summary.timeoutID) {
                clearTimeout(pr_summary.timeoutID);
                pr_summary.timeoutID = -1;
            }
            pr_summary.timeoutID = setTimeout(() => {
                let text =  $("#targettext").val();
                $(".summarize_button").prop("disabled", text.trim().length == 0 );
            }, 200);
        });
        /*if (params.login) {
            let authenticated = false;
            $("#logindialog").dialog({
                modal: true,
                closeOnEscape:false,
                beforeClose: function() {
                    return authenticated;
                },
                width:320,
                buttons: {
                  "ログイン": function() {
                    let jsondata = {username:$('#userid').val(), password:$('#password').val()};
                    let dlg = $(this);
                    pr_summary.postJson(params.path + "/auth", jsondata, 
                        function(hjson_data) { 
                            pr_summary.sessionId = hjson_data.sessionId;
                            $('#errmsg').text(""); 
                            authenticated = true; 
                            dlg.dialog("close");},
                        function() { $('#errmsg').text("ログイン出来ません。") } );
                    }
                }
            });
        }*/

        $("#stopprogress").on("click",function(event){
            pr_summary.canceled = true;
            event.preventDefault();
            pr_summary.showLoader(false);
            
        });
        $('#logout').click(function(e) {
            e.preventDefault();
            document.cookie = "sessionid=; max-age=0";
            document.cookie = "user=; max-age=0";
            window.location.href = "/login/?redirect=" + params.path;
        });
    },

    showLoader(show, enableCancel=false) {
        if (show) {
            $('.loader_wrapper').show();
            $('button').css('pointer-events','none');
            $('.ui-button,.ui-button-icon').css('pointer-events','none');
            $('#targettext,#prompt,#resulttext').prop('disabled', true);

        } else {
            $('.loader_wrapper').hide();
            $('#progress_msg').text("");
            $('button').css('pointer-events','auto');
            $('.ui-button,.ui-button-icon').css('pointer-events','auto');
            $('#targettext,#prompt,#resulttext').prop('disabled', false);
        }
        if (enableCancel) {
            $("#stopprogress").show();
            pr_summary.canceled = false;
        } else {
            $("#stopprogress").hide();
        }
    },

    getSummary:function() {
        let text = $("#targettext").val();
        let prompt = $("#prompt").val();
        let mode = $('input:radio[name="mode"]:checked').val();
        $("#resulttext").val(""); 
                
        pr_summary.showLoader(true, true);
        let param = {'prompt':prompt, 'text':text, 'mode':mode};
        Object.assign(param, pr_summary.testmode);
        $.post(params.path + "/summary", param)
            .done(function(data) {
                let requestId = data.requestId;
                pr_summary.requestId = requestId;
                console.log("getSummary pr_summary.requestId:"  + requestId);
                pr_summary.getDataProgressive(requestId);
        });
    },

    getDataProgressive:function(requestId) {
        $.post(params.path + "/getprogress", {'requestId':requestId, 'canceled':pr_summary.canceled ? 1 : 0})
            .done(function(data){
            if (!data.result || pr_summary.requestId != requestId) {
                console.log("getDataProgressive data nothing... requestId:" + requestId);
                return;
            }
            console.log(data);

            if (data.error || pr_summary.canceled) {
                if (data.error) {
                    toastr.error(data.errormsg, '', {timeOut: 0, extendedTimeOut:0, closeButton: true})
                }
                pr_summary.requestId = "";
                pr_summary.showLoader(false);
                return
            }

            if ('summary' in data) {
                let text = $("#resulttext").val(); 
                $("#resulttext").val(text + data["summary"]); 
            }
            if (data['reset']) {
                $("#resulttext").val("");
                $('#progress_msg').text(pr_summary.makeProgessMssage(data));
                pr_summary.getDataProgressive(requestId);
            } else if (data.result && !data['end']) {
                pr_summary.getDataProgressive(requestId);
                return;
            } else {
                pr_summary.showLoader(false);
            }
           
        });        
    },

    makeProgessMssage:function(data) {
        if (data.is_final) {
            return '最終的な処理中';
        } else {
            return '分割テキストの処理中 ' + data.progress + ' / ' + data.total ;
        }
    },

    /*doneGetSummary:function(data) {
        try {

            $("#showtext").val("showtext-diff");
            pr_summary.testData = data;
        } catch (e) {
            pr_summary.showLoader(false);
            pr_summary.requestId = "";
            console.log(e)
        }
    },*/

    reset:function(section) {
        $('#ex_prompt_1').trigger("click");
    },

    postJson:function(url, data, success, failed) {
        $.ajax({
            type:"post",                // method = "POST"
            url:url,        // POST送信先のURL
            data:JSON.stringify(data),  // JSONデータ本体
            contentType: 'application/json', // リクエストの Content-Type
            dataType: "json",           // レスポンスをJSONとしてパースする
        }).done(function(hjson_data,status,xhr) {
            //console.log(hjson_data);
            //pr_summary.access_token = hjson_data.access_token;
            success(hjson_data);
        }).fail(function() {
            failed();
        });
    }
};

// $.ajaxを退避
/*var orgAjax = $.ajax;
// $.ajaxをカスタマイズする
function customAjax(ajaxArgs) {
    var settings = $.extend({}, $.ajaxSettings, ajaxArgs);
    if (pr_summary.access_token) {
        if (!settings['headers']) {
            settings['headers'] = {};
        }
        let h = settings['headers'];
        h['Authorization'] = "JWT " + pr_summary.access_token;            
    }
    var deferred_org = $.Deferred();
    var jqXHR_org = orgAjax(settings)
        .then(
            function cmnDone(data, textStatus, jqXHR) {
                // 個別のdone()を呼び出す
                deferred_org.resolveWith(this, [data, textStatus, jqXHR])
            },
            function cmnFail(jqXHR, textStatus, errorThrown) {
                // 個別のfail()を呼び出す
                deferred_org.rejectWith(this, [jqXHR, textStatus, errorThrown]);
            }
        )
        .catch((e) => {
            // 個別のdoneで発生した例外をcatchできる
            console.trace(e);
        });
    return $.extend({}, jqXHR_org, deferred_org);
}
// $.ajaxを上書き
$.ajax = customAjax;*/

$(document).ready(function(){
	pr_summary.init();
});
