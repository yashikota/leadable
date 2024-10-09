import Vue from 'vue'
import App from './App.vue'
import './index.css'
import axios from 'axios'
import VueAxios from 'vue-axios'

Vue.config.productionTip = false
Vue.use(VueAxios, axios)

axios.defaults.baseURL = process.env.VUE_APP_API_URL
axios.defaults.withCredentials = true
axios.defaults.xsrfHeaderName = 'X-CSRF-Token'

new Vue({
  render: h => h(App),
}).$mount('#app')
