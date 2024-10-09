<template>
  <div id="app">
    <nav class="flex items-center justify-between bg-gray-800 text-white p-4">
      <h1 class="text-2xl">Leadable</h1>
    </nav>
    <div class="container mx-auto p-4">
      <div @dragenter="dragEnter" @dragleave="dragLeave" @dragover.prevent @drop.prevent="dropFile" :class="{enter: isEnter}" class="flex justify-center items-center bg-gray-200 rounded-lg p-2 border-dotted border-2 border-black mb-4 h-40 hover:bg-gray-300">
        <p class="text-lg">Drop pdf files here</p>
      </div>
      <p v-if="error" class="w-full rounded-lg p-2 mb-4 bg-red-100 text-black">{{ error }}</p>
      <div class="mb-4">
        <p :class="file">{{ file.name }}</p>
      </div>
      <button id="translate" @click="translate" class="bg-indigo-600 rounded-lg p-2 mb-4 w-full text-white hover:bg-indigo-500">Translate</button>
      <button id="download" v-if="isTranslate" @click="download" class="bg-sky-600 rounded-lg p-2 mb-4 w-full text-white hover:bg-indigo-500">Download translated file</button>
    </div>
  </div>
</template>

<script>

export default {
  name: 'App',
  data() {
    return {
      isEnter: false,
      error: "",
      file: [],
      isTranslate: false,
    }
  },
  methods: {
    dragEnter() {
      this.isEnter = true
    },
    dragLeave() {
      this.isEnter = false
    },
    dropFile(e) {
      this.isEnter = false
      this.file = e.dataTransfer.files[0]
      if (this.file.type !== 'application/pdf') {
        this.error = "Please upload a pdf file"
        return
      }
      this.error = ""
      console.log(this.file)
    },
    async translate() {
      // send files to backend
      if (!this.file) {
        this.error = "Please upload a file"
        return
      } else if (this.file.type !== 'application/pdf') {
        this.error = "Please upload a pdf file"
        return
      }
      const formData = new FormData()
      formData.append('file', this.file)
      const response = await this.axios.post('/translate', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      if (response.status === 200) {
        this.error = ""
        this.isTranslate = true
        return
      } else {
        this.error = response.data.message
      }
    },
    async download() {
      // download translated file
      const response = await this.axios.get(`/download/${this.file.name}`, {
        responseType: 'blob'
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', this.file.name)
      document.body.appendChild(link)
      link.click()
    }
  }
}
</script>
