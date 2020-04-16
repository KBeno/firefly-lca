import requests
import logging
import json
from typing import Mapping, Union, MutableMapping, List
from json import JSONDecodeError
from pathlib import Path
from pprint import pformat

import dill
import pandas as pd
from eppy.modeleditor import IDF

from firepy.tools.optimization import Parameter
from firepy.model.building import Building
from firepy.calculation.lca import LCACalculation
from firepy.calculation.cost import CostCalculation

logger = logging.getLogger(__name__)

class RemoteClient:

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.url = '{host}:{port}'.format(host=self.host, port=self.port)

    def setup(self,
              name: str,
              epw: Path = None,
              weather_data: Path = None,
              idf: IDF = None,
              model: Building = None,
              parameters: MutableMapping[str, Parameter] = None,
              lca_calculation: LCACalculation = None,
              cost_calculation: CostCalculation = None,
              energy_calculation: str = None,
              init_db: bool = True) -> str:
        """
        Setup the server with the following options. The options can also be set independently.

        :param name: Name of the calculation setup tp create or update
        :param epw: Path to epw file for weather data for simulation
        :param weather_data: Path to csv weather data for steady state energy calculation
        :param idf: eppy IDF model of the building
        :param model: converted firepy model of the building
        :param parameters: dict of firepy Parameters to use for parametric definition
        :param lca_calculation:
        :param cost_calculation:
        :param energy_calculation: 'simulation' or 'steady_state'
        :param init_db: set True (default) to create results database for the setup
        :return: success message
        """
        url = self.url + '/setup'

        logger.info('Setting up calculation: {n} at: {u}'.format(n=name, u=self.url))

        success = {}

        if epw is not None:
            logger.debug('Setting up EPW on server')
            with epw.open('r') as epw_file:
                epw_text = epw_file.read()
            # change windows type newline characters to unix type
            epw_text = epw_text.replace('\r\n', '\n')
            response = requests.post(url=url, params={'name': name, 'type': 'epw'}, data=epw_text)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['epw'] = response.text

        if weather_data is not None:
            logger.debug('Setting up weather data on server')
            weather = pd.read_csv(str(weather_data), header=[0,1], index_col=[0,1])
            content = dill.dumps(weather)
            response = requests.post(url=url, params={'name': name, 'type': 'weather_data'}, data=content)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['weather'] = response.text

        if idf is not None:
            logger.debug('Setting up IDF on server')
            idf_text = idf.idfstr()
            response = requests.post(url=url, params={'name': name, 'type': 'idf'}, data=idf_text)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['idf'] = response.text

        if model is not None:
            logger.debug('Setting up model on server')
            model_dump = dill.dumps(model)
            response = requests.post(url=url, params={'name': name, 'type': 'model'}, data=model_dump)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['model'] = response.text

        if parameters is not None:
            logger.debug('Setting up parameters on server')
            param_dump = dill.dumps(parameters)
            response = requests.post(url=url, params={'name': name, 'type': 'parameters'}, data=param_dump)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['parameters'] = response.text

        if lca_calculation is not None:
            logger.debug('Setting up LCA Calculation on server')
            lca_dump = dill.dumps(lca_calculation)
            response = requests.post(url=url, params={'name': name, 'type': 'lca_calculation'}, data=lca_dump)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['LCA Calculation'] = response.text

        if cost_calculation is not None:
            logger.debug('Setting up Cost Calculation on server')
            cost_dump = dill.dumps(cost_calculation)
            response = requests.post(url=url, params={'name': name, 'type': 'cost_calculation'}, data=cost_dump)
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['Cost Calculation'] = response.text

        if init_db:
            logger.debug('Initiating result database on server')
            response = requests.post(url=url, params={'name': name, 'type': 'database'})
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['Database'] = response.text

        if energy_calculation:
            if energy_calculation not in ['simulation', 'steady_state']:
                return 'Energy calculation type can be one of the following: simulation / steady_state'
            logger.debug('Setting up Energy Calculation type on server')
            response = requests.post(url=url,
                                     params={'name': name, 'type': 'energy_calculation', 'mode': energy_calculation})
            logger.debug('Response from server: ' + response.text)
            if not response.text.startswith('OK'):
                return response.text
            else:
                success['Energy Calculation'] = response.text

        return '\n' + pformat(success)

    def calculate(self, name: str, parameters: Mapping[str, Union[float, int, str]]):
        """
        Calculate the impact based on the parameters sent in the args of the request
        Model is updated, calculations are made and results are written in the database
        This is the entry point for external optimization algorithms

        :param name: Name of the calculation setup
        :param parameters: Parameters as a dict
        :return: result of the evaluation function as a dict
        """
        url = self.url + '/calculate'
        payload = {'name': name}
        payload.update(parameters)
        response = requests.get(url=url, params=payload)
        try:
            return response.json()
        except ValueError:
            return response.text

    def status(self):
        """
        Get status of server (setups and result tables)
        :return:
        """
        url = self.url + '/status'
        response = requests.get(url=url)
        try:
            return response.json()
        except ValueError:
            return response.text

    def results(self, name: str) -> pd.DataFrame:
        url = self.url + '/results'
        response = requests.get(url=url, params={'name': name})
        try:
            df = pd.read_json(response.json(), orient='split')
            return df
        except JSONDecodeError:
            return response.text

    def cleanup(self, name: str, target: str = None) -> str:
        """
        Cleanup server from stored data if target is not specified both will be deleted
        Prompts for confirmation

        :param name: name of the calculation setup
        :param target: 'results' / 'simulations'
        :return: message
        """
        url = self.url + '/cleanup'

        if target == 'results' or target is None:
            logger.warning('Result database will be cleared for setup: {n}'.format(n=name))
        if target == 'simulations' or target is None:
            logger.warning('Simulation results will be deleted for setup: {n}'.format(n=name))

        if input('Are you sure? (y/n): ') == 'y':
            response = requests.get(url=url, params={'name': name, 'target': target})
            return response.text
        else:
            logger.warning('Cleanup cancelled')

    def reinstate(self, name: str, calc_id: str) -> Mapping:
        """
        Same as calculate() but the results are not saved to the database and the parameters are
        retrieved from the result database based on the calculation id
        Use this to update the state of the server to further analyse the model

        :param name:
        :param calc_id:
        :return:
        """
        url = self.url + '/reinstate'
        response = requests.get(url=url, params={'name': name, 'id': calc_id})
        try:
            return response.json()
        except JSONDecodeError:
            return response.text

    def instate(self, name: str, parameters: Mapping[str, Union[float, int, str]],
                options: Mapping = None) -> Mapping:
        """
        Update state of server for the desired parameters and evaluate.
        Calculation results will not be saved to database.

        :param name: Name of the calculation setup
        :param parameters: parameters as a dict to run calculation for
        :param options: simulation options in the following patter
            {
                'outputs': 'all' or {
                    'zone': [
                        'heating' / 'cooling' / 'lights' / 'infiltration' / 'solar gains' / 'glazing loss' /
                        'opaque loss' /'ventilation' / 'equipment' / 'people' ],
                    'surface': [
                        'opaque loss' / 'glazing loss' / 'glazing gain' ]
                },
                'output_resolution': 'runperiod' / 'runperiod' / 'annual' / 'monthly' / 'daily' / 'hourly' / 'timestep',
                'clear_existing_variables': True
            }
        :return: result, simulation id and calculation time in a dict
        """
        url = self.url + '/instate'
        payload = {'name': name}
        payload.update(parameters)
        if options is not None:
            response = requests.post(url=url, params=payload, data=json.dumps(options))
        else:
            response = requests.get(url=url, params=payload)
        try:
            return response.json()
        except JSONDecodeError:
            return response.text

    def get_model(self, name: str) -> Building:
        """
        Return the actual model from the server

        :param name:
        :return:
        """
        url = self.url + '/model'
        response = requests.get(url=url, params={'name': name})
        try:
            model: Building = dill.loads(response.content)
            return model
        except dill.UnpicklingError:
            return response.text

    def get_params(self, name: str) -> Mapping:
        url = self.url + '/parameters'
        response = requests.get(url=url, params={'name': name})
        try:
            return response.json()
        except JSONDecodeError:
            return response.text

    def get_full_params(self, name: str) -> List[Parameter]:
        """
        Get Parameter objects from server
        :param name: name of the calculation setup
        :return: list with Parameter objects
        """
        url = self.url + '/parameters/full'
        response = requests.get(url=url, params={'name': name})
        try:
            param_dict = dill.loads(response.content)
            params: List[Parameter] = [p for p in param_dict.values()]
            return params
        except dill.UnpicklingError:
            return response.text

    def get_lca(self, name: str) -> LCACalculation:
        url = self.url + '/lca'
        response = requests.get(url=url, params={'name': name})
        try:
            calc: LCACalculation = dill.loads(response.content)
            return calc
        except dill.UnpicklingError:
            return response.text

    def get_cost(self, name: str) -> CostCalculation:
        url = self.url + '/cost'
        response = requests.get(url=url, params={'name': name})
        try:
            calc: CostCalculation = dill.loads(response.content)
            return calc
        except dill.UnpicklingError:
            return response.text

    def get_energy(self, name: str, calc_id: str = None,
                   variables: List[str] = None,
                   typ: str = 'zone',
                   period: str = 'runperiod') -> pd.DataFrame:
        """
        Retrieves the energy calculation results from the server. If steady state calculation is used,
        the result is a DataFrame with columns: 'heating' 'cooling', 'lights. If simulation is used,
        the result is specified with the other input parameters

        :param name: name of the calculation setup
        :param calc_id: id of a previously run simulation (omitted is steady state calculation)
        :param variables: variables to get from the simulation (omitted is steady state calculation)
        :param typ: 'zone' (default) / 'surface' / 'balance' (omitted is steady state calculation)
        :param period: 'runperiod' (default) / 'annual' / 'monthly' / 'daily' / 'hourly' / 'timestep'
            (omitted is steady state calculation)
        :return: pandas DataFrame with the requested data
        """
        url = self.url + '/energy'
        if variables is None:
            variables = ['heating', 'cooling', 'lights']
        response = requests.get(url=url, params={'name': name,
                                                 'id': calc_id,
                                                 'variables': variables,
                                                 'type': typ,
                                                 'period': period})
        try:
            df = pd.read_json(response.json(), orient='split')
            return df
        except JSONDecodeError:
            return response.text

    def get_energy_detailed(self, name: str, calc_id: str,
                            variable: str,
                            typ: str,
                            period: str) -> pd.DataFrame:
        url = self.url + '/energy/detailed'

        response = requests.get(url=url, params={'name': name,
                                                 'id': calc_id,
                                                 'variable': variable,
                                                 'type': typ,
                                                 'period': period})
        try:
            df = pd.read_json(response.json(), orient='split')
            return df
        except JSONDecodeError:
            return response.text