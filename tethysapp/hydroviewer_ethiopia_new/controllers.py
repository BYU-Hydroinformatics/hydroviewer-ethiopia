from django.shortcuts import render
from tethys_sdk.permissions import login_required
from tethys_sdk.gizmos import *
from django.http import HttpResponse, JsonResponse
from tethys_sdk.permissions import has_permission
from tethys_sdk.base import TethysAppBase

import os
import requests
from requests.auth import HTTPBasicAuth
import json
import numpy as np

from csv import writer as csv_writer
import scipy.stats as sp
import datetime as dt
import ast
import plotly.graph_objs as go
import geoglows

from .app import HydroviewerEthiopiaNew as app
from .helpers import *
base_name = __package__.split('.')[-1]

BYU_ENDPOINT = 'https://tethys2.byu.edu/localsptapi/api/'


def set_custom_setting(defaultModelName, defaultWSName):

    from tethys_apps.models import TethysApp
    db_app = TethysApp.objects.get(package=app.package)
    custom_settings = db_app.custom_settings

    db_setting = db_app.custom_settings.get(name='default_model_type')
    db_setting.value = defaultModelName
    db_setting.save()

    db_setting = db_app.custom_settings.get(name='default_watershed_name')
    db_setting.value = defaultWSName
    db_setting.save()


def home(request):

    # Check if we have a default model. If we do, then redirect the user to the default model's page
    default_model = app.get_custom_setting('default_model_type')
    if default_model:
        model_func = switch_model(default_model)
        if model_func is not 'invalid':
            return globals()[model_func](request)
        else:
            return home_standard(request)
    else:
        return home_standard(request)


def home_standard(request):
    model_input = SelectInput(display_text='',
                              name='model',
                              multiple=False,
                              options=[('Select Model', ''), ('ECMWF-RAPID', 'ecmwf')],
                              initial=['Select Model'],
                              original=True)

    zoom_info = TextInput(display_text='',
                          initial=json.dumps(app.get_custom_setting('zoom_info')),
                          name='zoom_info',
                          disabled=True)

    # Retrieve a geoserver engine and geoserver credentials.
    geoserver_engine = app.get_spatial_dataset_service(
        name='main_geoserver', as_engine=True)

    my_geoserver = geoserver_engine.endpoint.replace('rest', '')

    geoserver_base_url = my_geoserver
    geoserver_workspace = app.get_custom_setting('workspace')
    region = app.get_custom_setting('region')
    extra_feature = app.get_custom_setting('extra_feature')
    layer_name = app.get_custom_setting('layer_name')

    geoserver_endpoint = TextInput(display_text='',
                                   initial=json.dumps([geoserver_base_url, geoserver_workspace,
                                                       region, extra_feature, layer_name]),
                                   name='geoserver_endpoint',
                                   disabled=True)

    context = {
        "base_name": base_name,
        "model_input": model_input,
        "zoom_info": zoom_info,
        "geoserver_endpoint": geoserver_endpoint
    }

    return render(request, '{0}/home.html'.format(base_name), context)


def ecmwf(request):

    # Can Set Default permissions : Only allowed for admin users
    can_update_default = has_permission(request, 'update_default')

    if(can_update_default):
        defaultUpdateButton = Button(
            display_text='Save',
            name='update_button',
            style='success',
            attributes={
                'data-toggle': 'tooltip',
                'data-placement': 'bottom',
                'title': 'Save as Default Options for WS'
            })
    else:
        defaultUpdateButton = False

    # Check if we need to hide the WS options dropdown.
    hiddenAttr = ""
    if app.get_custom_setting('show_dropdown') and app.get_custom_setting('default_model_type') and app.get_custom_setting('default_watershed_name'):
        hiddenAttr = "hidden"

    default_model = app.get_custom_setting('default_model_type')
    init_model_val = request.GET.get('model', False) or default_model or 'Select Model'
    init_ws_val = app.get_custom_setting('default_watershed_name') or 'Select Watershed'

    model_input = SelectInput(display_text='',
                              name='model',
                              multiple=False,
                              options=[('Select Model', ''), ('ECMWF-RAPID', 'ecmwf')],
                              initial=[init_model_val],
                              classes=hiddenAttr,
                              original=True)

    # Retrieve a geoserver engine and geoserver credentials.
    geoserver_engine = app.get_spatial_dataset_service(
        name='main_geoserver', as_engine=True)

    geos_username = geoserver_engine.username
    geos_password = geoserver_engine.password
    my_geoserver = geoserver_engine.endpoint.replace('rest', '')

    watershed_list = [['Select Watershed', '']]  # + watershed_list
    res2 = requests.get(my_geoserver + 'rest/workspaces/' + app.get_custom_setting('workspace') +
                        '/featuretypes.json', auth=HTTPBasicAuth(geos_username, geos_password), verify=False)

    for i in range(len(json.loads(res2.content)['featureTypes']['featureType'])):
        raw_feature = json.loads(res2.content)['featureTypes']['featureType'][i]['name']
        if 'drainage_line' in raw_feature and any(n in raw_feature for n in app.get_custom_setting('keywords').replace(' ', '').split(',')):
            feat_name = raw_feature.split('-')[0].replace('_', ' ').title() + ' (' + \
                raw_feature.split('-')[1].replace('_', ' ').title() + ')'
            if feat_name not in str(watershed_list):
                watershed_list.append([feat_name, feat_name])

    # Add the default WS if present and not already in the list
    if default_model == 'ECMWF-RAPID' and init_ws_val and init_ws_val not in str(watershed_list):
        watershed_list.append([init_ws_val, init_ws_val])

    watershed_select = SelectInput(display_text='',
                                   name='watershed',
                                   options=watershed_list,
                                   initial=[init_ws_val],
                                   original=True,
                                   classes=hiddenAttr,
                                   attributes={'onchange': "javascript:view_watershed();"+hiddenAttr}
                                   )

    zoom_info = TextInput(display_text='',
                          initial=json.dumps(app.get_custom_setting('zoom_info')),
                          name='zoom_info',
                          disabled=True)

    # Retrieve a geoserver engine and geoserver credentials.
    geoserver_engine = app.get_spatial_dataset_service(
        name='main_geoserver', as_engine=True)

    my_geoserver = geoserver_engine.endpoint.replace('rest', '')

    geoserver_base_url = my_geoserver
    geoserver_workspace = app.get_custom_setting('workspace')
    region = app.get_custom_setting('region')
    extra_feature = app.get_custom_setting('extra_feature')
    layer_name = app.get_custom_setting('layer_name')

    geoserver_endpoint = TextInput(display_text='',
                                   initial=json.dumps([geoserver_base_url, geoserver_workspace,
                                                       region, extra_feature, layer_name]),
                                   name='geoserver_endpoint',
                                   disabled=True)

    context = {
        "base_name": base_name,
        "model_input": model_input,
        "watershed_select": watershed_select,
        "zoom_info": zoom_info,
        "geoserver_endpoint": geoserver_endpoint,
        "defaultUpdateButton": defaultUpdateButton
    }

    return render(request, '{0}/ecmwf.html'.format(base_name), context)


def get_warning_points(request):
    get_data = request.GET
    if get_data['model'] == 'ECMWF-RAPID':
        try:
            watershed = get_data['watershed']
            subbasin = get_data['subbasin']

            res20 = requests.get(
                app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetWarningPoints/?watershed_name=' +
                watershed + '&subbasin_name=' + subbasin + '&return_period=20',
                headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

            res10 = requests.get(
                app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetWarningPoints/?watershed_name=' +
                watershed + '&subbasin_name=' + subbasin + '&return_period=10',
                headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

            res2 = requests.get(
                app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetWarningPoints/?watershed_name=' +
                watershed + '&subbasin_name=' + subbasin + '&return_period=2',
                headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

            return JsonResponse({
                "success": "Data analysis complete!",
                "warning20": json.loads(res20.content)["features"],
                "warning10": json.loads(res10.content)["features"],
                "warning2": json.loads(res2.content)["features"]
            })
        except Exception as e:
            print(str(e))
            return JsonResponse({'error': 'No data found for the selected reach.'})
    else:
        pass


def ecmwf_get_time_series(request):
    get_data = request.GET
    try:
        # model = get_data['model']
        comid = get_data['comid']


        # New api
        stats = geoglows.streamflow.forecast_stats(comid)
        ensembles = geoglows.streamflow.forecast_ensembles(comid)
        r_periods = geoglows.streamflow.return_periods(comid)

        forecast_plot = geoglows.streamflow.forecast_plot(stats, r_periods, comid, outformat='plotly_html')
        prob_table = geoglows.streamflow.probabilities_table(stats, ensembles, r_periods)

        return JsonResponse(dict(plot=forecast_plot, table=prob_table))

    except Exception as e:
        print(str(e))
        return JsonResponse({'error': 'No data found for the selected reach.'})


def get_time_series(request):
    return ecmwf_get_time_series(request)


def get_available_dates(request):
    get_data = request.GET

    comid = get_data['comid']
    comid = int(comid)

    # New api
    avail_dates = geoglows.streamflow.available_dates(comid, api_source=BYU_ENDPOINT, api_key=None)

    # res = requests.get(
    #     app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetAvailableDates/?watershed_name=' +
    #     watershed + '&subbasin_name=' + subbasin, verify=False,
    #     headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')})
    #
    # dates = []
    # for date in eval(res.content):
    #     if len(date) == 10:
    #         date_mod = date + '000'
    #         date_f = dt.datetime.strptime(date_mod, '%Y%m%d.%H%M').strftime('%Y-%m-%d %H:%M')
    #     else:
    #         date_f = dt.datetime.strptime(date, '%Y%m%d.%H%M').strftime('%Y-%m-%d %H:%M')
    #     dates.append([date_f, date, watershed, subbasin, comid])
    #
    # dates.append(['Select Date', dates[-1][1]])
    # dates.reverse()

    # return JsonResponse({
    #     "success": "Data analysis complete!",
    #     "available_dates": json.dumps(dates)
    # })

    return JsonResponse(avail_dates)


def get_historic_data(request):
    """""
    Returns ERA Interim hydrograph
    """""

    get_data = request.GET

    try:
        comid = get_data['comid']


        # New api
        rperiods = geoglows.streamflow.return_periods(comid)
        historic_sim = geoglows.streamflow.historic_simulation(comid)

        return JsonResponse(dict(plot=geoglows.streamflow.historical_plot(historic_sim,
                                                                          rperiods, comid, outformat='plotly_html')))

    except Exception as e:
        print(str(e))
        return JsonResponse({'error': 'No historic data found for the selected reach.'})


def get_flow_duration_curve(request):
    get_data = request.GET

    try:
        # model = get_data['model']
        watershed = get_data['watershed']
        subbasin = get_data['subbasin']
        comid = get_data['comid']
        tot_drain_area = get_data['tot_drain_area']
        region = get_data['region']
        units = 'metric'

        # Not on new api




        era_res = requests.get(
            app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetHistoricData/?watershed_name=' +
            watershed + '&subbasin_name=' + subbasin + '&reach_id=' + comid + '&return_format=csv',
            headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

        era_pairs = era_res.content.splitlines()
        era_pairs.pop(0)

        era_values = []

        for era_pair in era_pairs:
            era_pair = era_pair.decode('utf-8')
            era_values.append(float(era_pair.split(',')[1]))

        sorted_daily_avg = np.sort(era_values)[::-1]

        # ranks data from smallest to largest
        ranks = len(sorted_daily_avg) - sp.rankdata(sorted_daily_avg,
                                                    method='average')

        # calculate probability of each rank
        prob = [100*(ranks[i] / (len(sorted_daily_avg) + 1))
                for i in range(len(sorted_daily_avg))]

        flow_duration_sc = go.Scatter(
            x=prob,
            y=sorted_daily_avg,
        )

        layout = go.Layout(title="Flow-Duration Curve<br><sub>{0} ({1}): {2}<br>Total upstream drainage area: {3} km<sup>2</sup></sub>".format(
            watershed, subbasin, comid, tot_drain_area),
            xaxis=dict(
            title='Exceedance Probability (%)',),
            yaxis=dict(
            title='Streamflow ({}<sup>3</sup>/s)'
            .format(get_units_title(units)),
            type='log',
            autorange=True),
            showlegend=False)

        chart_obj = PlotlyView(
            go.Figure(data=[flow_duration_sc],
                      layout=layout)
        )

        context = {
            'gizmo_object': chart_obj,
        }

        return render(request, '{0}/gizmo_ajax.html'.format(base_name), context)

    except Exception as e:
        print(str(e))
        return JsonResponse({'error': 'No historic data found for calculating flow duration curve.'})


def get_return_period_ploty_info(request, datetime_start, datetime_end,
                                 band_alt_max=-9999):
    """
    Get shapes and annotations for plotly plot
    """

    # Return Period Section
    return_period_data = get_return_periods(request)
    return_max = float(return_period_data["max"])
    return_20 = float(return_period_data["twenty"])
    return_10 = float(return_period_data["ten"])
    return_2 = float(return_period_data["two"])

    # plotly info section
    shapes = [
        # return 20 band
        dict(
            type='rect',
            xref='x',
            yref='y',
            x0=datetime_start,
            y0=return_20,
            x1=datetime_end,
            y1=max(return_max, band_alt_max),
            line=dict(width=0),
            fillcolor='rgba(128, 0, 128, 0.4)',
        ),
        # return 10 band
        dict(
            type='rect',
            xref='x',
            yref='y',
            x0=datetime_start,
            y0=return_10,
            x1=datetime_end,
            y1=return_20,
            line=dict(width=0),
            fillcolor='rgba(255, 0, 0, 0.4)',
        ),
        # return 2 band
        dict(
            type='rect',
            xref='x',
            yref='y',
            x0=datetime_start,
            y0=return_2,
            x1=datetime_end,
            y1=return_10,
            line=dict(width=0),
            fillcolor='rgba(255, 255, 0, 0.4)',
        ),
    ]
    annotations = [
        # return max
        dict(
            x=datetime_end,
            y=return_max,
            xref='x',
            yref='y',
            text='Max. ({:.1f})'.format(return_max),
            showarrow=False,
            xanchor='left',
        ),
        # return 20 band
        dict(
            x=datetime_end,
            y=return_20,
            xref='x',
            yref='y',
            text='20-yr ({:.1f})'.format(return_20),
            showarrow=False,
            xanchor='left',
        ),
        # return 10 band
        dict(
            x=datetime_end,
            y=return_10,
            xref='x',
            yref='y',
            text='10-yr ({:.1f})'.format(return_10),
            showarrow=False,
            xanchor='left',
        ),
        # return 2 band
        dict(
            x=datetime_end,
            y=return_2,
            xref='x',
            yref='y',
            text='2-yr ({:.1f})'.format(return_2),
            showarrow=False,
            xanchor='left',
        ),
    ]

    return shapes, annotations


def get_historic_data_csv(request):
    """""
    Returns ERA Interim data as csv
    """""

    get_data = request.GET

    try:
        # model = get_data['model']
        watershed = get_data['watershed_name']
        subbasin = get_data['subbasin_name']
        comid = get_data['reach_id']

        # New api (Historical simulation returns a csv)
        rperiods = geoglows.streamflow.return_periods(comid, 'o314noias', api_source=geoglows.streamflow.BYU_ENDPOINT)
        historic_sim = geoglows.streamflow.historic_simulation(comid, 'o314noias', return_format='csv', api_source=geoglows.streamflow.BYU_ENDPOINT)




        era_res = requests.get(
            app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetHistoricData/?watershed_name=' +
            watershed + '&subbasin_name=' + subbasin + '&reach_id=' + comid + '&return_format=csv',
            headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

        qout_data = era_res.content.splitlines()
        qout_data.pop(0)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=historic_streamflow_{0}_{1}_{2}.csv'.format(watershed,
                                                                                                            subbasin,
                                                                                                            comid)

        writer = csv_writer(response)

        writer.writerow(['datetime', 'streamflow (m3/s)'])

        for row_data in qout_data:
            writer.writerow(row_data.split(','))

        return response

    except Exception as e:
        print(str(e))
        return JsonResponse({'error': 'No historic data found.'})


def get_forecast_data_csv(request):
    """""
    Returns Forecast data as csv
    """""

    get_data = request.GET

    try:
        # model = get_data['model']
        watershed = get_data['watershed_name']
        subbasin = get_data['subbasin_name']
        comid = get_data['reach_id']
        if get_data['startdate'] != '':
            startdate = get_data['startdate']
        else:
            startdate = 'most_recent'

        # New api
        stats = geoglows.streamflow.forecast_stats(comid, 'o314noias', api_source=geoglows.streamflow.BYU_ENDPOINT)
        ensembles = geoglows.streamflow.forecast_ensembles(comid, 'o314noias', return_format='csv', api_source=geoglows.streamflow.BYU_ENDPOINT)
        r_periods = geoglows.streamflow.return_periods(comid, 'o314noias', api_source=geoglows.streamflow.BYU_ENDPOINT)

        forecast_plot = geoglows.streamflow.forecast_plot(stats, r_periods, comid, outformat='plotly_html')
        prob_table = geoglows.streamflow.probabilities_table(stats, ensembles, r_periods)





        res = requests.get(
            app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetForecast/?watershed_name=' +
            watershed + '&subbasin_name=' + subbasin + '&reach_id=' + comid + '&forecast_folder=' +
            startdate + '&return_format=csv',
            headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')}, verify=False)

        qout_data = res.content.splitlines()
        qout_data.pop(0)

        init_time = qout_data[0].split(',')[0].split(' ')[0]
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename=streamflow_forecast_{0}_{1}_{2}_{3}.csv'.format(watershed,
                                                                                                                subbasin,
                                                                                                                comid,
                                                                                                                init_time)

        writer = csv_writer(response)
        writer.writerow(['datetime', 'high_res (m3/s)', 'max (m3/s)', 'mean (m3/s)', 'min (m3/s)', 'std_dev_range_lower (m3/s)',
                         'std_dev_range_upper (m3/s)'])

        for row_data in qout_data:
            writer.writerow(row_data.split(','))

        return response

    except Exception as e:
        print(str(e))
        return JsonResponse({'error': 'No forecast data found.'})


# def get_daily_seasonal_streamflow_chart(request):
#     """
#     Returns daily seasonal streamflow chart for unique river ID
#     """
#     units = request.GET.get('units')
#     seasonal_data_file, river_id, watershed_name, subbasin_name =\
#         validate_historical_data(request.GET,
#                                  "seasonal_average*.nc",
#                                  "Seasonal Average")
#
#     with rivid_exception_handler('Seasonal Average', river_id):
#         with xarray.open_dataset(seasonal_data_file) as seasonal_nc:
#             seasonal_data = seasonal_nc.sel(rivid=river_id)
#             base_date = datetime.datetime(2017, 1, 1)
#             day_of_year = \
#                 [base_date + datetime.timedelta(days=ii)
#                  for ii in range(seasonal_data.dims['day_of_year'])]
#             season_avg = seasonal_data.average_flow.values
#             season_std = seasonal_data.std_dev_flow.values
#
#             season_avg[season_avg < 0] = 0
#
#             avg_plus_std = season_avg + season_std
#             avg_min_std = season_avg - season_std
#
#             avg_plus_std[avg_plus_std < 0] = 0
#             avg_min_std[avg_min_std < 0] = 0
#
#     if units == 'english':
#         # convert from m3/s to ft3/s
#         season_avg *= M3_TO_FT3
#         avg_plus_std *= M3_TO_FT3
#         avg_min_std *= M3_TO_FT3
#
#     # generate chart
#     avg_scatter = go.Scatter(
#         name='Average',
#         x=day_of_year,
#         y=season_avg,
#         line=dict(
#             color='#0066ff'
#         )
#     )
#
#     std_plus_scatter = go.Scatter(
#         name='Std. Dev. Upper',
#         x=day_of_year,
#         y=avg_plus_std,
#         fill=None,
#         mode='lines',
#         line=dict(
#             color='#98fb98'
#         )
#     )
#
#     std_min_scatter = go.Scatter(
#         name='Std. Dev. Lower',
#         x=day_of_year,
#         y=avg_min_std,
#         fill='tonexty',
#         mode='lines',
#         line=dict(
#             color='#98fb98',
#         )
#     )
#
#     layout = go.Layout(
#         title="Daily Seasonal Streamflow<br>"
#               "<sub>{0} ({1}): {2}</sub>"
#               .format(watershed_name, subbasin_name, river_id),
#         xaxis=dict(
#             title='Day of Year',
#             tickformat="%b"),
#         yaxis=dict(
#             title='Streamflow ({}<sup>3</sup>/s)'
#                   .format(get_units_title(units)))
#     )
#
#     chart_obj = PlotlyView(
#         go.Figure(data=[std_plus_scatter,
#                         std_min_scatter,
#                         avg_scatter],
#                   layout=layout)
#     )
#
#     context = {
#         'gizmo_object': chart_obj,
#     }
#
#     return render(request,
#                   'streamflow_prediction_tool/gizmo_ajax.html',
#                   context)

def setDefault(request):
    get_data = request.GET
    set_custom_setting(get_data.get('ws_name'), get_data.get('model_name'))
    return JsonResponse({'success': True})


def get_units_title(unit_type):
    """
    Get the title for units
    """
    units_title = "m"
    if unit_type == 'english':
        units_title = "ft"
    return units_title


def forecastpercent(request):

    # Check if its an ajax post request
    if request.is_ajax() and request.method == 'GET':

        watershed = request.GET.get('watershed')
        subbasin = request.GET.get('subbasin')
        reach = request.GET.get('comid')
        date = request.GET.get('startdate')
        if date == '':
            forecast = 'most_recent'
        else:
            forecast = str(date)
# res = requests.get(app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetWatersheds/',
    #                    headers={'Authorization': 'Token ' + app.get_custom_setting('spt_token')})
        request_params = dict(watershed_name=watershed, subbasin_name=subbasin, reach_id=reach,
                              forecast_folder=forecast)
        request_headers = dict(Authorization='Token ' + app.get_custom_setting('spt_token'))
        ens = requests.get(app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetEnsemble/',
                           params=request_params, headers=request_headers, verify=False)

        request_params1 = dict(watershed_name=watershed, subbasin_name=subbasin, reach_id=reach)
        rpall = requests.get(app.get_custom_setting('api_source') + '/apps/streamflow-prediction-tool/api/GetReturnPeriods/',
                             params=request_params1, headers=request_headers, verify=False)

        dicts = ens.content.splitlines()
        dictstr = []

        rpdict = ast.literal_eval(rpall.content.decode('utf-8'))
        rpdict.pop('max', None)

        rivperc = {}
        riverpercent = {}
        rivpercorder = {}

        for q in rpdict:
            rivperc[q] = {}
            riverpercent[q] = {}

        dictlen = len(dicts)
        for i in range(1, dictlen):
            dictstr.append(dicts[i].decode('utf-8').split(","))

        for rps in rivperc:
            rp = float(rpdict[rps])
            for b in dictstr:
                date = b[0][:10]
                if date not in rivperc[rps]:
                    rivperc[rps][date] = []
                length = len(b)
                for x in range(1, length):
                    flow = float(b[x])
                    if x not in rivperc[rps][date] and flow > rp:
                        rivperc[rps][date].append(x)
            for e in rivperc[rps]:
                riverpercent[rps][e] = float(len(rivperc[rps][e])) / 51.0 * 100

        for keyss in rivperc:
            data = riverpercent[keyss]
            ordered_data = sorted(list(data.items()), key=lambda x: dt.datetime.strptime(x[0], '%Y-%m-%d'))
            rivpercorder[keyss] = ordered_data

        rivdates = []
        rivperctwo = []
        rivpercten = []
        rivperctwenty = []

        for a in rivpercorder['two']:
            rivdates.append(a[0])
            rivperctwo.append(a[1])

        for s in rivpercorder['ten']:
            rivpercten.append(s[1])

        for d in rivpercorder['twenty']:
            rivperctwenty.append(d[1])

        formatteddates = [str(elem)[-4:] for elem in rivdates]
        formattedtwo = ["%.0f" % elem for elem in rivperctwo]
        formattedten = ["%.0f" % elem for elem in rivpercten]
        formattedtwenty = ["%.0f" % elem for elem in rivperctwenty]

        formatteddates = formatteddates[:len(formatteddates) - 5]
        formattedtwo = formattedtwo[:len(formattedtwo) - 5]
        formattedten = formattedten[:len(formattedten) - 5]
        formattedtwenty = formattedtwenty[:len(formattedtwenty) - 5]

        dataformatted = {'percdates': formatteddates, 'two': formattedtwo, 'ten': formattedten,
                         'twenty': formattedtwenty}

        return JsonResponse(dataformatted)
