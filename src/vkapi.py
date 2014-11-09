import time
import logging
import requests
import codecs
import os
import sys
import json

logger = logging.getLogger(__name__)

class VkError(Exception):
    pass

class VkAPI(object):    
  
    PROFILE_FIELDS = ','.join(['nickname', 'screen_name', 'sex', 'bdate', 'city', 'relation', 'country', 'education', 
                               'universities', 'schools', 'connections', 'relation', 'relatives', 'interests', 'books'])
    
    def __init__(self, token=None):
        self.session = requests.Session()
        self.session.headers['Accept'] = 'application/json'
        self.session.headers['Content-Type'] = 'application/x-www-form-urlencoded'
        
        self.token = token
        self.requests_times = []
        
    def _do_api_call(self, method, params):
        self._pause_before_request()
        
        if self.token:
            params['access_token'] = self.token
        params['v'] = '5.26'
            
        param_str = '&'.join(['%s=%s' % (k, v) for k, v in params.iteritems()])
        url = 'https://api.vk.com/method/%s?%s' % (method, param_str)
        logger.debug('API request: %s' % (method))
        
        response = self.session.get(url)
        if response.status_code is not 200:
            time.sleep(10)
            response = self.session.get(url)
            if response.status_code is not 200:
                raise VkError('Can\'t get %s, code %s' % (url, response.status_code))        
                
        json = response.json()
        if 'response' not in json:
            raise VkError('Api call error %s - %s' % (url, json))
        
        return json['response'] 
        
    def _pause_before_request(self):
        if len(self.requests_times) > 2:
            first = self.requests_times[0]
            diff = time.time() - first
            if diff < 1.:
                logger.info('Sleepping for %s sec' % (1. - diff))
                time.sleep(1.- diff)
            self.requests_times = self.requests_times[1:]            
        self.requests_times.append(time.time())
        
    def get_user_profile(self, user_id):    
        profile = self._do_api_call('users.get', { 'user_ids' :  user_id,  'fields' : VkAPI.PROFILE_FIELDS})                    
        return profile[0]           
                            
    def get_user_profiles(self, user_ids):                      
        result = []        
        for offset in xrange(0, len(user_ids) / 100 + 1):            
            start, end = offset * 100, (offset + 1) * 100 
            ids = ','.join([str(user_id) for user_id in user_ids[start:end]])        
            response = self._do_api_call('users.get', { 'user_ids' :  ids,  'fields' : VkAPI.PROFILE_FIELDS})
            result.extend(response)
        return result
    
    def get_group_users(self, group_id):
        members_count = self._do_api_call('groups.getById', { 'group_id' :  group_id,  'fields' : 'members_count'})[0]['members_count'] 
        user_ids = set()
        for offset in xrange(0, members_count / 1000 + 1):
            response = self._do_api_call('groups.getMembers', { 'group_id' :  group_id, 'offset' : offset * 1000})
            user_ids.update(response['items'])
        return list(user_ids)
    
    def get_friends(self, user_id):
        response = self._do_api_call('friends.get', { 'user_id' : user_id,   'fields' : VkAPI.PROFILE_FIELDS})                    
        return response['items']
                    
    def close():
        self.session.close()        

def get_user_network(user_id, depth):    
    api = VkAPI()       
    all_profiles = dict()       
        
    def load_user_network(user_id, depth):    
        if depth == 0:
            return
            
        if user_id not in all_profiles:
            logger.info('Getting profile for id%s' % user_id)
            all_profiles[user_id] = api.get_user_profile(user_id)                     
                
        logger.info('Getting friends for id%s' % user_id)    
        friends = api.get_friends(user_id)
        for friend in friends:
            friend_id = int(friend['id'])
            if friend_id not in all_profiles:
                all_profiles[friend_id] = friend
                load_user_network(friend_id, depth - 1)                                
        all_profiles[user_id]['friends'] = [int(friend['id']) for friend in friends]        
    
    load_user_network(user_id, depth)    
    return all_profiles 
        

if __name__ == '__main__':
    logger.setLevel(logging.INFO)
    logger.addHandler(logging.StreamHandler())
    
    try:        
        os.mkdir('data')
    except:
        pass
        
    for user_id in sys.argv[1:]:     
        logger.info('Getting network for id%s' % user_id)
        with codecs.open('data/egonet_%s.json' % user_id, 'w', 'utf-8') as f:
            user_network = get_user_network(user_id, 2)
            f.write(json.dumps(user_network, ensure_ascii=False, encoding='utf-8', indent=1))        